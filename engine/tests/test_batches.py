from datetime import timedelta

import pytest
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import AnthropicLLM, BatchItem, FakeLLM
from marsad.fetch.http import PoliteClient
from marsad.models import AiBatch, AiUsage, Document, RightsLevel, Stage
from marsad.seed import seed_glossary, seed_taxonomy
from marsad.worker import run_once
from tests.helpers import make_source, mock_transport

FEED = "https://example-review.test/feed/"
GRAY = "Deterrence in the Gray Zone: Lessons for Allied Planners"
SHORT = "Short note without full text"
PAGE = "<html><body><article><h1>Short note</h1>" + "".join(
    f"<p>Paragraph {i} of the short note discusses naval logistics and readiness in some detail here.</p>"
    for i in range(10)) + "</article></body></html>"


@pytest.fixture
def setup(db, settings, fixture_bytes):
    seed_taxonomy(db)
    seed_glossary(db)
    make_source(db, rights=RightsLevel.a)
    settings.batch_enabled = True
    settings.batch_max_importance = 3
    http = PoliteClient(settings, transport=mock_transport({
        FEED: (200, fixture_bytes("feed.xml")),
        "https://example-review.test/2026/11/short-note": (200, PAGE, {"content-type": "text/html"}),
    }))
    return http


def doc(db, title):
    db.expire_all()
    return db.scalar(select(Document).where(Document.title_en == title))


def run(session_factory, llm, http, settings, n):
    return [run_once(session_factory, llm, http, settings) for _ in range(n)]


def test_low_importance_goes_through_batch_high_importance_does_not(db, session_factory, settings, setup):
    llm = FakeLLM(demo_handler, batch_rounds=1)
    counts = run(session_factory, llm, setup, settings, 3)  # submitted in cycle 2, still running in cycle 3
    assert any(c.get("batch_submitted") for c in counts)
    short, gray = doc(db, SHORT), doc(db, GRAY)
    assert gray.stage == Stage.review  # importance 4: translated immediately
    assert short.stage == Stage.summarized and short.in_batch_id is not None  # waiting for the batch
    run(session_factory, llm, setup, settings, 2)
    short = doc(db, SHORT)
    assert short.stage == Stage.review and short.in_batch_id is None
    assert len(short.translation.paragraphs_ar) == len(short.paragraphs_en) == 10
    tasks = {t for t, _ in llm.calls}
    assert "translate_batch" in tasks
    usage = db.scalars(select(AiUsage)).all()
    batch_cost = sum(u.cost_usd for u in usage if u.task == "translate_batch")
    assert batch_cost > 0, [(u.task, u.cost_usd) for u in usage]
    assert db.scalar(select(AiBatch)).status == "collected"
    sync_short = [p for t, p in llm.calls if t == "translate" and p["title"] == SHORT]
    assert sync_short == []  # nothing for this item went through the full-price path


def test_missing_and_errored_batch_results_are_retried_synchronously(db, session_factory, settings, setup):
    def handler(task, payload):
        if task == "translate_batch":
            ids = [p["id"] for p in payload["paragraphs"]]
            if 0 in ids:
                raise RuntimeError("request failed inside the batch")
            return {"paragraphs": [{"id": i, "ar": f"فقرة {i}"} for i in ids if i != 3], "notes": []}
        if task == "translate":
            return {"paragraphs": [{"id": p["id"], "ar": f"فقرة {p['id']}"} for p in payload["paragraphs"]], "notes": []}
        return demo_handler(task, payload)

    settings.chunk_words = 60  # several chunks per item
    llm = FakeLLM(handler, batch_rounds=0)
    run(session_factory, llm, setup, settings, 6)
    short = doc(db, SHORT)
    assert short.stage == Stage.review
    assert short.translation.paragraphs_ar == [f"فقرة {i}" for i in range(10)]
    retried = [p for t, p in llm.calls if t == "translate" and p["title"] == SHORT]
    assert retried and set(p["id"] for p in retried[0]["paragraphs"]) >= {0, 3}


def test_batch_that_never_ends_falls_back_after_26_hours(db, session_factory, settings, setup):
    llm = FakeLLM(demo_handler, batch_rounds=10_000)
    run(session_factory, llm, setup, settings, 4)
    batch = db.scalar(select(AiBatch))
    assert batch is not None and batch.status == "submitted"
    batch.created_at = batch.created_at - timedelta(hours=27)
    db.commit()
    run(session_factory, llm, setup, settings, 2)
    assert doc(db, SHORT).stage == Stage.review


def test_batch_disabled_keeps_everything_synchronous(db, session_factory, settings, setup):
    settings.batch_enabled = False
    llm = FakeLLM(demo_handler)
    run(session_factory, llm, setup, settings, 6)
    assert doc(db, SHORT).stage == Stage.review and db.scalar(select(AiBatch)) is None


def test_anthropic_batch_request_shape():
    sent = {}

    class Batches:
        def create(self, requests):
            sent["requests"] = requests
            return type("B", (), {"id": "msgbatch_1"})()

    client = type("C", (), {})()
    client.messages = type("M", (), {})()
    client.messages.batches = Batches()
    llm = AnthropicLLM(client=client)
    bid = llm.batch_submit([BatchItem(custom_id="d1-c0-ab", model="claude-opus-5-5", system="SYS", user="{}",
                                      schema={"type": "object"}, max_tokens=5000, effort="medium")])
    req = sent["requests"][0]
    assert bid == "msgbatch_1" and req["custom_id"] == "d1-c0-ab"
    params = req["params"]
    assert "fallbacks" not in params and "betas" not in params  # not allowed in batches
    assert params["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}, "effort": "medium"}
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
