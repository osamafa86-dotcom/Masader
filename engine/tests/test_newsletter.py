from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.demo import load_demo
from marsad.models import Digest, DigestDelivery, Subscriber, User
from marsad.newsletter import service
from marsad.newsletter.mailer import FakeMailer
from marsad.seed import seed_all


@pytest.fixture
def nl(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    db.add(User(email="ed@example.org", name="محرر", password_hash=hash_password("secret-pass")))
    db.commit()
    mailer = FakeMailer()
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                embedder=None, mailer=mailer))
    token = api.post("/api/editor/login", json={"email": "ed@example.org", "password": "secret-pass"}).json()["token"]
    return api, mailer, {"Authorization": f"Bearer {token}"}


def token_from(mail: dict) -> str:
    return mail["text"].split("token=")[1].split()[0]


def subscribe_and_confirm(api, mailer, email, **prefs) -> str:
    assert api.post("/api/subscribe", json={"email": email, **prefs}).status_code == 202
    token = token_from(mailer.sent[-1])
    assert api.post("/api/subscribe/confirm", json={"token": token}).json()["active"] is True
    return token


def test_double_opt_in_is_idempotent(nl, db):
    api, mailer, _ = nl
    r = api.post("/api/subscribe", json={"email": "  Reader@Example.org "})
    assert r.status_code == 202 and len(mailer.sent) == 1
    mail = mailer.sent[0]
    assert mail["to"] == "reader@example.org" and "/subscribe/confirm?token=" in mail["text"]
    # Submitting again within 10 minutes neither duplicates the row nor re-sends.
    api.post("/api/subscribe", json={"email": "reader@example.org"})
    assert len(mailer.sent) == 1
    assert len(db.scalars(select(Subscriber)).all()) == 1
    token = token_from(mail)
    first = api.post("/api/subscribe/confirm", json={"token": token}).json()
    second = api.post("/api/subscribe/confirm", json={"token": token}).json()
    assert first == second and first["active"] is True and first["email"] == "re***@example.org"
    # Already active: a new request sends nothing and the response looks the same.
    r2 = api.post("/api/subscribe", json={"email": "reader@example.org"})
    assert r2.json() == r.json() and len(mailer.sent) == 1


def test_invalid_email_and_tokens(nl):
    api, _, _ = nl
    assert api.post("/api/subscribe", json={"email": "not-an-email"}).status_code == 422
    assert api.post("/api/unsubscribe", json={"token": "forged-token"}).status_code == 404
    assert api.get("/api/subscription/forged-token").status_code == 404


def test_unsubscribe_only_affects_token_owner(nl, db):
    api, mailer, _ = nl
    a = subscribe_and_confirm(api, mailer, "a@example.org")
    b = subscribe_and_confirm(api, mailer, "b@example.org")
    assert api.post("/api/unsubscribe", json={"token": a}).json()["active"] is False
    assert api.get(f"/api/subscription/{b}").json()["active"] is True


def test_digest_requires_editor_send_and_filters_by_preferences(nl, db, settings, session_factory):
    api, mailer, h = nl
    subscribe_and_confirm(api, mailer, "all@example.org")
    subscribe_and_confirm(api, mailer, "arctic@example.org", topics=["arctic"])
    subscribe_and_confirm(api, mailer, "cyber@example.org", topics=["cyber"])
    subscribe_and_confirm(api, mailer, "kw@example.org", keywords=["الإمداد"])
    mailer.sent.clear()

    draft = service.ensure_weekly_draft(db, settings)
    assert draft is not None and len(draft.document_ids) == 3
    assert service.ensure_weekly_draft(db, settings) is None  # one open draft at a time
    # Nothing goes out without an editor pressing send.
    assert service.deliver_pending(db, mailer, settings) == 0 and mailer.sent == []

    api.patch(f"/api/editor/digests/{draft.id}", headers=h, json={"intro_ar": "مقدمة المحرر", "document_ids": draft.document_ids + [9999]})
    r = api.post(f"/api/editor/digests/{draft.id}/send", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "sending"
    assert api.post(f"/api/editor/digests/{draft.id}/send", headers=h).status_code == 409

    db.expire_all()  # the worker always starts from a fresh session
    assert service.deliver_pending(db, mailer, settings) == 3
    by_to = {m["to"]: m for m in mailer.sent}
    assert set(by_to) == {"all@example.org", "arctic@example.org", "kw@example.org"}  # cyber: nothing matched
    assert "مقدمة المحرر" in by_to["all@example.org"]["text"]
    assert by_to["arctic@example.org"]["text"].count("/articles/") == 1
    assert "التنافس في القطب الشمالي" in by_to["arctic@example.org"]["html"]
    assert "الإمداد البحري" in by_to["kw@example.org"]["html"]
    headers = by_to["all@example.org"]["headers"]
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "/unsubscribe?token=" in headers["List-Unsubscribe"]
    db.expire_all()
    assert db.get(Digest, draft.id).status == "sent"
    statuses = {d.status for d in db.scalars(select(DigestDelivery))}
    assert statuses == {"sent", "skipped"}


def test_failed_delivery_is_recorded(nl, db, settings):
    api, mailer, h = nl
    subscribe_and_confirm(api, mailer, "bounce@example.org")
    mailer.fail_for.add("bounce@example.org")
    draft = service.create_draft(db, settings)
    api.post(f"/api/editor/digests/{draft.id}/send", headers=h)
    db.expire_all()
    service.deliver_pending(db, mailer, settings)
    d = db.scalar(select(DigestDelivery))
    assert d.status == "failed" and "simulated" in d.error


def test_weekly_draft_waits_seven_days(nl, db, settings):
    api, mailer, h = nl
    draft = service.create_draft(db, settings)
    draft.status = "sent"
    db.commit()
    assert service.ensure_weekly_draft(db, settings, at=draft.period_end + timedelta(days=3)) is None
    assert api.post("/api/editor/digests", headers=h).status_code == 409  # nothing new published since


def test_subscribe_without_mailer_is_unavailable(db, session_factory, settings):
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                embedder=None, mailer=None))
    assert api.post("/api/subscribe", json={"email": "x@example.org"}).status_code == 503
