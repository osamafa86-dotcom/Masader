import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.demo import load_demo
from marsad.models import ApiClient, Document, User
from marsad.seed import seed_all


@pytest.fixture
def v1(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    db.add(User(email="admin@example.org", name="مدير", password_hash=hash_password("secret-pass"), role="admin"))
    db.commit()
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                embedder=None, mailer=None))
    token = api.post("/api/editor/login", json={"email": "admin@example.org", "password": "secret-pass"}).json()["token"]
    admin = {"Authorization": f"Bearer {token}"}
    r = api.post("/api/editor/api-clients", headers=admin, json={"name": "مركز أبحاث", "rate_limit_per_minute": 5})
    assert r.status_code == 201
    return api, admin, r.json()


def test_key_required_and_hashed(v1, db):
    api, _, created = v1
    assert api.get("/v1/articles").status_code == 401
    assert api.get("/v1/articles", headers={"X-API-Key": "mrsd_forged"}).status_code == 401
    key = created["key"]
    assert key.startswith("mrsd_") and created["key_prefix"] == key[:12]
    stored = db.scalar(select(ApiClient))
    assert stored.key_hash != key and key not in stored.key_hash
    r = api.get("/v1/articles", headers={"X-API-Key": key})
    assert r.status_code == 200 and r.json()["meta"]["total"] == 5
    assert r.headers["X-RateLimit-Limit"] == "5" and r.headers["X-RateLimit-Remaining"] == "4"
    assert api.get("/v1/sources", headers={"Authorization": f"Bearer {key}"}).status_code == 200


def test_rate_limit_and_revocation(v1):
    api, admin, created = v1
    h = {"X-API-Key": created["key"]}
    codes = [api.get("/v1/topics", headers=h).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    r = api.get("/v1/topics", headers=h)
    assert r.status_code == 429 and 1 <= int(r.headers["Retry-After"]) <= 61
    api.patch(f"/api/editor/api-clients/{created['id']}", headers=admin, json={"is_active": False})
    assert api.get("/v1/topics", headers=h).status_code == 401
    listed = api.get("/api/editor/api-clients", headers=admin).json()
    assert listed[0]["requests_30d"] >= 7 and "key" not in listed[0]


def test_rights_rules_apply_to_api(v1, db):
    api, _, created = v1
    h = {"X-API-Key": created["key"]}
    by_title = {d.title_en: d.id for d in db.scalars(select(Document))}
    summary_only = api.get(f"/v1/articles/{by_title['Arctic Competition and the Alliance']}", headers=h).json()["data"]
    assert summary_only["publish_level"] == "summary" and summary_only["body"] is None
    full = api.get(f"/v1/articles/{by_title['Deterrence in the Gray Zone: Lessons for Allied Planners']}", headers=h).json()["data"]
    assert full["publish_level"] == "full" and len(full["body"]) == 7


def test_filters_and_search(v1):
    api, _, created = v1
    h = {"X-API-Key": created["key"]}
    assert api.get("/v1/articles", headers=h, params={"source": "demo-journal"}).json()["meta"]["total"] == 2
    assert api.get("/v1/articles", headers=h, params={"since": "2099-01-01"}).json()["meta"]["total"] == 0
    res = api.get("/v1/search", headers=h, params={"q": "ردع"}).json()
    assert res["meta"]["total"] == 1 and res["mode"] == "keyword"
    assert api.get("/v1/openapi.json").status_code == 200  # docs are public, data is not


def test_only_admins_manage_keys(v1, db):
    api, admin, _ = v1
    db.scalar(select(User)).role = "editor"
    db.commit()
    assert api.get("/api/editor/api-clients", headers=admin).status_code == 403
