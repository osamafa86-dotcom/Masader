import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.fetch.http import PoliteClient
from marsad.fetch.rss import parse_feed
from marsad.journals import clean_abstract
from marsad.models import Document, PublishLevel, RightsLevel, Stage, User
from marsad.seed import seed_glossary, seed_taxonomy
from marsad.worker import run_once
from tests.helpers import make_source, mock_transport

FEED = "https://journal.test/feed/"
COALITION = "Coalition Intelligence Sharing and the Limits of Trust"
SATELLITES = "Strategic Warning in the Age of Commercial Satellites"


def test_feed_metadata_and_abstract_cleaning(fixture_bytes):
    entries = {e.title: e for e in parse_feed(fixture_bytes("journal_feed.xml"))}
    meta = entries[COALITION].meta
    assert meta["volume"] == "41" and meta["issue"] == "6"
    assert meta["start_page"] == "812" and meta["end_page"] == "835"
    assert meta["doi"] == "10.1080/02684527.2026.2401234"
    assert entries[COALITION].authors == ["Maria Lopez", "Tom Reed"]
    assert entries[SATELLITES].meta.get("open_access") is True
    abstract = clean_abstract(entries[COALITION].summary)
    assert abstract.startswith("Intelligence sharing within coalitions")
    assert clean_abstract(entries["Correction"].summary) == ""


@pytest.fixture
def journal(db, session_factory, settings, fixture_bytes):
    seed_taxonomy(db)
    seed_glossary(db)
    src = make_source(db, slug="fixjournal", rights=RightsLevel.c, feed_url=FEED, kind="journal")
    src.kind, src.content_mode = "journal", "abstract"
    db.add(User(email="ed@example.org", name="محرر", password_hash=hash_password("secret-pass"), role="admin"))
    db.commit()
    calls: list[str] = []
    article_page = "<html><body><article>" + "".join(
        f"<p>Open access paragraph {i} about warning, satellites and the pressure to declassify assessments quickly.</p>"
        for i in range(12)) + "</article></body></html>"
    http = PoliteClient(settings, transport=mock_transport({
        FEED: (200, fixture_bytes("journal_feed.xml")),
        "https://journal.test/doi/full/10.1080/02684527.2026.2405555?af=R": (200, article_page, {"content-type": "text/html"}),
    }, calls))
    llm = FakeLLM(demo_handler)

    def run(rounds=6):
        for _ in range(rounds):
            run_once(session_factory, llm, http, settings)
        db.expire_all()

    return {"run": run, "calls": calls, "llm": llm, "src": src}


def by_title(db, title):
    return db.scalar(select(Document).where(Document.title_en == title))


def test_journal_items_are_summarised_from_abstract_without_download(db, journal):
    journal["run"]()
    coalition = by_title(db, COALITION)
    assert coalition.stage == Stage.review
    assert coalition.paragraphs_en == [] and coalition.abstract_en.startswith("Intelligence sharing")
    assert coalition.meta["journal"] == "Fixjournal" and coalition.meta["issue"] == "6"
    assert coalition.translation.summary["abstract_only"] is True
    assert coalition.translation.paragraphs_ar is None
    sent = [p for task, p in journal["llm"].calls if task == "summarize" and p["title"] == COALITION][0]
    assert sent["abstract_only"] is True and sent["text"] == ""
    assert not [c for c in journal["calls"] if "/doi/" in c]  # never downloaded

    correction = by_title(db, "Correction")
    assert correction.stage == Stage.failed and "no abstract" in correction.error


def test_item_licence_reprocesses_with_full_text(db, journal, session_factory, settings):
    journal["run"]()
    sat = by_title(db, SATELLITES)
    app = create_app(settings=settings, factory=session_factory, llm=journal["llm"])
    api = TestClient(app)
    token = api.post("/api/editor/login", json={"email": "ed@example.org", "password": "secret-pass"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = api.post(f"/api/editor/items/{sat.id}/license", headers=h, json={"license": "CC BY 4.0", "evidence": "x"})
    assert r.status_code == 422  # evidence too short
    r = api.post(f"/api/editor/items/{sat.id}/license", headers=h,
                 json={"license": "CC BY 4.0", "evidence": "Open Access label on publisher page, checked 2026-11-20"})
    assert r.status_code == 200 and r.json()["stage"] == "discovered"
    journal["run"]()
    sat = by_title(db, SATELLITES)
    assert sat.max_level == PublishLevel.full and len(sat.paragraphs_en) >= 1
    assert sat.translation.paragraphs_ar is not None
    api.post(f"/api/editor/items/{sat.id}/publish", headers=h)
    public = api.get(f"/api/articles/{sat.id}").json()
    assert public["publish_level"] == "full" and public["license"] == "CC BY 4.0"
    assert "ترخيص المادة" in public["rights_note"]


def test_issue_table_of_contents(db, journal, session_factory, settings):
    journal["run"]()
    app = create_app(settings=settings, factory=session_factory, llm=journal["llm"])
    api = TestClient(app)
    token = api.post("/api/editor/login", json={"email": "ed@example.org", "password": "secret-pass"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    for title in (COALITION, SATELLITES):
        api.post(f"/api/editor/items/{by_title(db, title).id}/publish", headers=h)
    assert api.get("/api/sources/fixjournal/issues").json() == [
        {"volume": "41", "issue": "6", "count": 2, "latest": api.get("/api/sources/fixjournal/issues").json()[0]["latest"]}]
    toc = api.get("/api/sources/fixjournal/issues/41/6").json()
    assert [i["title_en"] for i in toc["items"]] == [SATELLITES, COALITION]  # ordered by start page 790, 812
    assert toc["items"][1]["basis"] == "abstract" and toc["items"][1]["meta"]["doi"].startswith("10.1080")
    assert api.get("/api/sources/fixjournal/issues/41/7").status_code == 404


def test_toc_mode_translates_title_only(db, session_factory, settings, fixture_bytes):
    seed_taxonomy(db)
    src = make_source(db, slug="tocjournal", rights=RightsLevel.c, feed_url=FEED)
    src.content_mode = "toc"
    db.commit()
    llm = FakeLLM(demo_handler)
    http = PoliteClient(settings, transport=mock_transport({FEED: (200, fixture_bytes("journal_feed.xml"))}))
    for _ in range(6):
        run_once(session_factory, llm, http, settings)
    db.expire_all()
    corr = by_title(db, "Correction")
    assert corr.stage == Stage.review
    assert corr.translation.summary["toc_only"] is True and corr.translation.summary["thesis_ar"] == ""
    assert not [p for t, p in llm.calls if t == "summarize" and p["title"] == "Correction"]
    # Items that do carry an abstract are still summarised from it.
    assert by_title(db, COALITION).translation.summary.get("abstract_only") is True
