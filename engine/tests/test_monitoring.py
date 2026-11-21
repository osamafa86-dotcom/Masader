from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.models import AiUsage, RawItem, Source, SystemState
from marsad.monitoring import find_problems, heartbeat, now, send_alerts
from marsad.newsletter.mailer import FakeMailer
from marsad.seed import seed_all
from tests.helpers import make_source


def test_strict_health_reports_stale_worker(db, session_factory, settings):
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler), embedder=None,
                                mailer=None))
    assert api.get("/api/health").json() == {"ok": True}
    assert api.get("/api/health?strict=1").status_code == 503  # never ran
    heartbeat(db, {"fetched": 2})
    r = api.get("/api/health?strict=1")
    assert r.status_code == 200 and r.json()["worker"]["last_cycle"] == {"fetched": 2}
    row = db.get(SystemState, "worker_heartbeat")
    row.updated_at = now() - timedelta(minutes=11)
    db.commit()
    assert api.get("/api/health?strict=1").status_code == 503


def test_alerts_detect_and_deduplicate(db, settings):
    seed_all(db)
    src = make_source(db, slug="broken")
    src.last_error, src.last_fetched_at, src.last_success_at = "HTTP 500", now(), now() - timedelta(days=2)
    db.add(AiUsage(task="translate", model="m", cost_usd=settings.daily_budget_usd * 0.9))
    db.commit()
    keys = {k for k, _ in find_problems(db, settings)}
    assert "source:broken" in keys and any(k.startswith("budget:") for k in keys)

    settings.alert_emails = "ops@example.org, lead@example.org"
    mailer = FakeMailer()
    assert send_alerts(db, mailer, settings) >= 2
    assert {m["to"] for m in mailer.sent} == {"ops@example.org", "lead@example.org"}
    assert "تعذّر رصد المصدر" in mailer.sent[0]["text"]
    assert send_alerts(db, mailer, settings) == 0  # same problems: not re-sent within 12 hours


def test_no_new_items_alert(db, settings):
    make_source(db, slug="quiet")
    db.add(RawItem(source_id=db.scalar(select(Source.id)), url="https://x.test/a", url_hash="h1",
                   discovered_at=now() - timedelta(hours=60)))
    db.commit()
    assert "no_new_items" in {k for k, _ in find_problems(db, settings)}
