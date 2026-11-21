import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.demo import load_demo
from marsad.models import Document, Stage, User
from marsad.sampling import current_sample
from marsad.seed import seed_all


@pytest.fixture
def ed(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)  # all published without human review
    for i, email in enumerate(["a@example.org", "b@example.org"]):
        db.add(User(email=email, name=f"محرر {i}", password_hash=hash_password("secret-pass")))
    db.commit()
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler), embedder=None, mailer=None))
    h = {}
    for email in ("a@example.org", "b@example.org"):
        tok = api.post("/api/editor/login", json={"email": email, "password": "secret-pass"}).json()["token"]
        h[email] = {"Authorization": f"Bearer {tok}"}
    return api, h


def test_weekly_sample_is_ten_percent_and_shrinks_when_checked(ed, db):
    api, h = ed
    sample = api.get("/api/editor/sample", headers=h["a@example.org"]).json()
    assert len(sample) == 1  # ceil(10% of 6)
    assert [d.id for d in current_sample(db)] == [sample[0]["id"]]  # stable within the week
    api.post(f"/api/editor/items/{sample[0]['id']}/sample", headers=h["a@example.org"], json={"result": "ok"})
    assert api.get("/api/editor/sample", headers=h["a@example.org"]).json() == []
    assert api.post(f"/api/editor/items/{sample[0]['id']}/sample", headers=h["a@example.org"],
                    json={"result": "maybe"}).status_code == 422


def test_assignment_and_my_queue(ed, db):
    api, h = ed
    doc = db.scalar(select(Document).where(Document.title_en.like("Arctic%")))
    doc.stage = Stage.review
    db.commit()
    b = db.scalar(select(User).where(User.email == "b@example.org"))
    r = api.post(f"/api/editor/items/{doc.id}/assign", headers=h["a@example.org"], json={"user_id": b.id})
    assert r.json()["assigned_to"] == b.id
    mine_b = api.get("/api/editor/queue", params={"mine": True}, headers=h["b@example.org"]).json()
    mine_a = api.get("/api/editor/queue", params={"mine": True}, headers=h["a@example.org"]).json()
    assert [x["id"] for x in mine_b["items"]] == [doc.id] and mine_a["total"] == 0
    assert len(api.get("/api/editor/users", headers=h["a@example.org"]).json()) == 2
