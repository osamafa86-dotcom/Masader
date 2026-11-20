from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.demo import load_demo
from marsad.models import Document, TrendReport, User
from marsad.seed import seed_all
from marsad.trends import compute, ensure_previous_month_draft, month_bounds, shift


def test_month_helpers():
    assert shift("2026-01", -1) == "2025-12" and shift("2026-12", 1) == "2027-01"
    start, end = month_bounds("2026-12")
    assert start == datetime(2026, 12, 1, tzinfo=timezone.utc) and end == datetime(2027, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        month_bounds("2026-13")


@pytest.fixture
def tr(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)  # five items, all published in November 2026
    # Move one item to October so there is a previous month to compare with.
    arctic = db.scalar(select(Document).where(Document.title_en == "Arctic Competition and the Alliance"))
    arctic.published_at = datetime(2026, 10, 20, tzinfo=timezone.utc)
    db.add(User(email="ed@example.org", name="محرر", password_hash=hash_password("secret-pass")))
    db.commit()
    llm = FakeLLM(demo_handler)
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=llm, embedder=None, mailer=None))
    tok = api.post("/api/editor/login", json={"email": "ed@example.org", "password": "secret-pass"}).json()["token"]
    return api, {"Authorization": f"Bearer {tok}"}, llm


def test_monthly_statistics(tr, db):
    stats = compute(db, "2026-11")
    assert stats["total"] == 4 and stats["previous_total"] == 1 and stats["small_sample"] is True
    topics = {r["slug"]: r for r in stats["topics"]}
    assert topics["intelligence"]["count"] == 2 and topics["intelligence"]["previous"] == 0
    assert topics["great-power"]["count"] == 0 and topics["great-power"]["previous"] == 1
    assert sum(w["count"] for w in stats["weeks"]) == 4
    assert {i["importance"] for i in stats["top_items"]} == {4}
    assert stats["rising_topics"][0]["slug"] == "intelligence"


def test_empty_month_is_explicit(tr):
    api, h, llm = tr
    r = api.get("/api/trends/2020-01").json()
    assert r["empty"] is True and r["total"] == 0 and r["topics"] == [] and r["report"] is None
    assert api.post("/api/editor/trends/2020-01/draft", headers=h).status_code == 409
    assert not [c for c in llm.calls if c[0] == "trend_narrative"]  # no narrative invented for no data
    assert api.get("/api/trends/2026-13").status_code == 422


def test_report_draft_review_publish(tr):
    api, h, llm = tr
    d = api.post("/api/editor/trends/2026-11/draft", headers=h).json()
    assert d["narrative_is_draft"] is True and "رُصدت 4 مادة" in d["narrative_ar"]
    sent = [p for t, p in llm.calls if t == "trend_narrative"][0]
    assert sent["total"] == 4 and "rising_topics" in sent  # the model only sees the computed numbers
    assert api.get("/api/trends/2026-11").json()["report"] is None  # drafts are not public
    assert api.post("/api/editor/trends/2026-11/publish", headers=h).status_code == 409
    api.patch("/api/editor/trends/2026-11", headers=h, json={"narrative_ar": "قراءة الشهر بعد مراجعة المحرر للأرقام."})
    assert api.post("/api/editor/trends/2026-11/publish", headers=h).status_code == 200
    assert api.get("/api/trends/2026-11").json()["report"]["narrative_ar"].startswith("قراءة الشهر")
    assert {"month": "2026-11", "report": True} in api.get("/api/trends/months").json()


def test_worker_drafts_previous_month_once(tr, db, settings):
    _, _, llm = tr
    december = datetime(2026, 12, 2, tzinfo=timezone.utc)
    assert ensure_previous_month_draft(db, llm, settings, at=december) is True
    assert ensure_previous_month_draft(db, llm, settings, at=december) is False
    assert db.scalar(select(TrendReport)).month == "2026-11"
    assert ensure_previous_month_draft(db, llm, settings, at=datetime(2020, 2, 1, tzinfo=timezone.utc)) is False
