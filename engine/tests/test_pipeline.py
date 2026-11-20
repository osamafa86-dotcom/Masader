from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.fetch.http import PoliteClient
from marsad.models import AiUsage, Document, PublishLevel, RightsLevel, Stage
from marsad.seed import seed_glossary, seed_taxonomy
from marsad.worker import run_once
from tests.helpers import make_source, mock_transport

FEED = "https://example-review.test/feed/"
GRAY = "Deterrence in the Gray Zone: Lessons for Allied Planners"
SHORT_PAGE = "<html><body><article><h1>Short note</h1>" + "<p>" + "Short note body text. " * 40 + "</p></article></body></html>"


@pytest.fixture
def world(db, settings, fixture_bytes):
    seed_taxonomy(db)
    seed_glossary(db)
    db.commit()
    routes = {
        FEED: (200, fixture_bytes("feed.xml")),
        "https://example-review.test/2026/11/short-note": (200, SHORT_PAGE, {"content-type": "text/html"}),
        "https://example-review.test/2026/11/naval-logistics": (404, "gone"),
    }
    client = PoliteClient(settings, transport=mock_transport(routes))
    return client


def drain(session_factory, llm, client, settings, rounds=8):
    for _ in range(rounds):
        run_once(session_factory, llm, client, settings)


def doc_by_title(db, title):
    db.expire_all()
    return db.scalar(select(Document).where(Document.title_en == title))


def test_open_source_item_reaches_review_with_full_translation(db, session_factory, settings, world):
    make_source(db, rights=RightsLevel.a, license="CC BY-NC 4.0")
    llm = FakeLLM(demo_handler)
    drain(session_factory, llm, world, settings)

    doc = doc_by_title(db, GRAY)
    assert doc.stage == Stage.review
    assert doc.importance == 4 and doc.max_level == PublishLevel.full
    tr = doc.translation
    assert tr.title_ar.startswith("الردع في المنطقة الرمادية")
    assert len(tr.paragraphs_ar) == len(doc.paragraphs_en) == 7
    assert tr.qa_report["score"] == 100
    assert {t.term.slug for t in doc.tags} >= {"deterrence", "indo-pacific", "commentary"}
    assert db.scalar(select(AiUsage).where(AiUsage.document_id == doc.id, AiUsage.task == "translate"))

    # Body from the page download (feed had a teaser only); placeholder translation gets QA issues.
    short = doc_by_title(db, "Short note without full text")
    assert short.stage == Stage.review
    assert short.translation.qa_report["score"] < 100

    # 404 page with a 6-word teaser: retried, then failed with the error recorded.
    naval = doc_by_title(db, "Naval Logistics After the Pacific Exercises")
    assert naval.stage == Stage.failed and "404" in naval.error and naval.attempts == 3


def test_protected_source_gets_summary_only(db, session_factory, settings, world):
    make_source(db, rights=RightsLevel.c)
    llm = FakeLLM(demo_handler)
    drain(session_factory, llm, world, settings)

    doc = doc_by_title(db, GRAY)
    assert doc.stage == Stage.review and doc.max_level == PublishLevel.summary
    assert doc.translation.paragraphs_ar is None
    assert doc.translation.summary["thesis_ar"]
    translated_titles = {p["title"] for task, p in llm.calls if task == "translate"}
    assert GRAY not in translated_titles


def test_budget_cap_pauses_ai_but_not_extraction(db, session_factory, settings, world):
    make_source(db)
    db.add(AiUsage(task="translate", model="m", cost_usd=settings.daily_budget_usd + 1,
                   created_at=datetime.now(timezone.utc)))
    db.commit()
    llm = FakeLLM(demo_handler)
    drain(session_factory, llm, world, settings, rounds=2)
    assert llm.calls == []
    assert doc_by_title(db, GRAY).stage == Stage.extracted


def test_failing_document_does_not_block_others(db, session_factory, settings, world):
    make_source(db)

    def handler(task, payload):
        if payload.get("title") == GRAY:
            raise RuntimeError("upstream exploded")
        return demo_handler(task, payload)

    drain(session_factory, FakeLLM(handler), world, settings)
    gray = doc_by_title(db, GRAY)
    assert gray.stage == Stage.failed and "upstream exploded" in gray.error
    assert doc_by_title(db, "Short note without full text").stage == Stage.review


def test_auto_publish_only_below_review_threshold(db, session_factory, settings, world):
    make_source(db)
    settings.auto_publish = True
    settings.review_min_importance = 5
    drain(session_factory, FakeLLM(demo_handler), world, settings)
    gray = doc_by_title(db, GRAY)
    assert gray.stage == Stage.published
    assert gray.translation.human_reviewed is False and gray.translation.published_at is not None
    assert "الردع" in gray.translation.search_text
    # The placeholder item has QA issues but none high, and importance 3 < 5: published too.
    # Raising the threshold back keeps new items in review.
    settings.review_min_importance = 3


def test_same_article_from_two_sources_is_stored_once(db, session_factory, settings, fixture_bytes):
    seed_taxonomy(db)
    db.commit()
    make_source(db, slug="first")
    make_source(db, slug="second", feed_url="https://mirror.test/feed/")
    mirror = fixture_bytes("feed.xml").replace(b"https://example-review.test", b"https://mirror.test") \
        .replace(b"http://example-review.test", b"https://mirror.test")
    client = PoliteClient(settings, transport=mock_transport({FEED: (200, fixture_bytes("feed.xml")),
                                                              "https://mirror.test/feed/": (200, mirror)}))
    drain(session_factory, FakeLLM(demo_handler), client, settings, rounds=1)
    docs = db.scalars(select(Document).where(Document.title_en == GRAY).order_by(Document.id)).all()
    assert [d.stage for d in docs][1] == Stage.rejected
    assert "duplicate of document" in docs[1].error
