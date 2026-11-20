import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.demo import load_demo
from marsad.embed import FakeEmbedder, embed_pending
from marsad.models import Document, Stage, User
from marsad.seed import seed_all


@pytest.fixture
def ed(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    embed_pending(db, FakeEmbedder())
    db.add(User(email="ed@example.org", name="محرر", password_hash=hash_password("secret-pass")))
    db.commit()
    settings.semantic_min_similarity = 0.05
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                embedder=FakeEmbedder(), mailer=None))
    tok = api.post("/api/editor/login", json={"email": "ed@example.org", "password": "secret-pass"}).json()["token"]
    ids = {d.title_en: d.id for d in db.scalars(select(Document))}
    return api, {"Authorization": f"Bearer {tok}"}, ids


def test_dossier_lifecycle(ed, db):
    api, h, ids = ed
    d = api.post("/api/editor/dossiers", headers=h, json={"title_ar": "الاستخبارات بين الحلفاء"}).json()
    assert d["status"] == "draft" and d["slug"]
    intel = [ids["Coalition Intelligence Sharing and the Limits of Trust"],
             ids["Strategic Warning in the Age of Commercial Satellites"]]
    api.patch(f"/api/editor/dossiers/{d['id']}", headers=h,
              json={"items": [{"document_id": intel[0], "note_ar": "نقطة البداية"}, {"document_id": intel[1]},
                              {"document_id": intel[0]}, {"document_id": 99999}]})
    got = api.get(f"/api/editor/dossiers/{d['id']}", headers=h).json()
    assert [i["id"] for i in got["items"]] == intel and got["items"][0]["note_ar"] == "نقطة البداية"

    assert api.post(f"/api/editor/dossiers/{d['id']}/publish", headers=h).status_code == 409  # no intro yet
    drafted = api.post(f"/api/editor/dossiers/{d['id']}/draft-intro", headers=h).json()
    assert drafted["intro_is_draft"] is True and "تجمع 2 مواد" in drafted["intro_ar"]
    r = api.post(f"/api/editor/dossiers/{d['id']}/publish", headers=h)
    assert r.status_code == 409 and "راجعها" in r.json()["detail"]  # a model draft cannot go out unreviewed
    api.patch(f"/api/editor/dossiers/{d['id']}", headers=h, json={"intro_ar": "مقدمة راجعها المحرر."})
    assert api.post(f"/api/editor/dossiers/{d['id']}/publish", headers=h).status_code == 200

    public = api.get(f"/api/dossiers/{d['slug']}").json()
    assert public["intro_ar"] == "مقدمة راجعها المحرر." and public["item_count"] == 2
    assert [x["slug"] for x in api.get("/api/dossiers").json()] == [d["slug"]]

    # Taking an item down removes it from the published dossier too.
    db.get(Document, intel[1]).stage = Stage.review
    db.commit()
    assert api.get(f"/api/dossiers/{d['slug']}").json()["item_count"] == 1


def test_unpublished_dossier_is_hidden(ed):
    api, h, _ = ed
    d = api.post("/api/editor/dossiers", headers=h, json={"title_ar": "ملف قيد الإعداد"}).json()
    assert api.get(f"/api/dossiers/{d['slug']}").status_code == 404
    second = api.post("/api/editor/dossiers", headers=h, json={"title_ar": "ملف قيد الإعداد"}).json()
    assert second["slug"] != d["slug"]


def test_suggestions_exclude_existing_items(ed):
    api, h, ids = ed
    d = api.post("/api/editor/dossiers", headers=h, json={"title_ar": "الردع"}).json()
    gray = ids["Deterrence in the Gray Zone: Lessons for Allied Planners"]
    sug = api.get(f"/api/editor/dossiers/{d['id']}/suggestions", headers=h, params={"q": "الردع"}).json()
    assert sug[0]["id"] == gray
    api.patch(f"/api/editor/dossiers/{d['id']}", headers=h, json={"items": [{"document_id": gray}]})
    sug = api.get(f"/api/editor/dossiers/{d['id']}/suggestions", headers=h).json()
    assert gray not in [s["id"] for s in sug] and len(sug) >= 1  # by closeness to the dossier's items
