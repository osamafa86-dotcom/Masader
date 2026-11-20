from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.demo import load_demo
from marsad.models import Document, Reader, ReaderLoginToken, SavedItem, Stage, Subscriber
from marsad.newsletter.mailer import FakeMailer
from marsad.seed import seed_all


@pytest.fixture
def acc(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    mailer = FakeMailer()
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                embedder=None, mailer=mailer))
    ids = {d.title_en: d.id for d in db.scalars(select(Document))}
    return api, mailer, ids


def link_token(mail) -> str:
    return mail["text"].split("token=")[1].split()[0]


def sign_in(api, mailer, email="reader@example.org") -> dict:
    assert api.post("/api/account/login", json={"email": email}).status_code == 202
    session = api.post("/api/account/verify", json={"token": link_token(mailer.sent[-1])}).json()["session_token"]
    return {"X-Reader-Token": session}


def test_magic_link_is_single_use_and_expires(acc, db):
    api, mailer, _ = acc
    api.post("/api/account/login", json={"email": "Reader@Example.org"})
    token = link_token(mailer.sent[-1])
    assert api.post("/api/account/verify", json={"token": token}).status_code == 200
    assert api.post("/api/account/verify", json={"token": token}).status_code == 400  # reused
    assert api.post("/api/account/verify", json={"token": "forged"}).status_code == 400

    api.post("/api/account/login", json={"email": "reader@example.org"})
    stale = link_token(mailer.sent[-1])
    for row in db.scalars(select(ReaderLoginToken).where(ReaderLoginToken.used_at.is_(None))):
        row.expires_at = row.expires_at - timedelta(hours=1)
    db.commit()
    assert api.post("/api/account/verify", json={"token": stale}).status_code == 400  # expired
    assert db.scalar(select(func.count()).select_from(Reader)) == 1


def test_link_requests_are_throttled(acc):
    api, mailer, _ = acc
    for _ in range(5):
        assert api.post("/api/account/login", json={"email": "spam@example.org"}).status_code == 202
    assert len(mailer.sent) == 3
    assert api.post("/api/account/login", json={"email": "nope"}).status_code == 422


def test_library_and_alerts(acc, db):
    api, mailer, ids = acc
    h = sign_in(api, mailer)
    assert api.get("/api/account/me").status_code == 401
    gray = ids["Deterrence in the Gray Zone: Lessons for Allied Planners"]
    assert api.put(f"/api/account/library/{gray}", headers=h, json={"note": "للفصل الثالث"}).json() == {"saved": True}
    assert api.put("/api/account/library/99999", headers=h, json={}).status_code == 404
    lib = api.get("/api/account/library", headers=h).json()
    assert lib[0]["note"] == "للفصل الثالث" and lib[0]["article"]["id"] == gray
    assert api.get("/api/account/me", headers=h).json()["saved_ids"] == [gray]

    # A taken-down item stays in the library, marked unavailable, without its content.
    db.get(Document, gray).stage = Stage.review
    db.commit()
    lib = api.get("/api/account/library", headers=h).json()
    assert lib[0]["available"] is False and lib[0]["article"] is None

    al = api.put("/api/account/alerts", headers=h, json={"active": True, "topics": ["arctic"]}).json()
    assert al == {"active": True, "topics": ["arctic"], "sources": [], "keywords": []}
    sub = db.scalar(select(Subscriber).where(Subscriber.email == "reader@example.org"))
    assert sub.confirmed_at is not None  # signing in proved the address
    assert len([m for m in mailer.sent if "أكّد اشتراكك" in m["subject"]]) == 0
    assert api.put("/api/account/alerts", headers=h, json={"active": False}).json()["active"] is False


def test_delete_account_removes_everything(acc, db):
    api, mailer, ids = acc
    h = sign_in(api, mailer, "gone@example.org")
    api.put(f"/api/account/library/{ids['Arctic Competition and the Alliance']}", headers=h, json={})
    api.put("/api/account/alerts", headers=h, json={"active": True})
    assert api.delete("/api/account", headers=h).json() == {"deleted": True}
    assert api.get("/api/account/me", headers=h).status_code == 401
    for model in (Reader, SavedItem, Subscriber, ReaderLoginToken):
        assert db.scalar(select(func.count()).select_from(model)) == 0, model


def test_logout(acc):
    api, mailer, _ = acc
    h = sign_in(api, mailer)
    api.post("/api/account/logout", headers=h)
    assert api.get("/api/account/me", headers=h).status_code == 401
