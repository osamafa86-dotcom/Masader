import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.fetch.http import PoliteClient
from marsad.models import AuditLog, Document, RightsLevel, Source, Stage, User
from marsad.seed import seed_glossary, seed_taxonomy
from marsad.worker import run_once
from tests.helpers import make_source, mock_transport

FEED = "https://example-review.test/feed/"
GRAY = "Deterrence in the Gray Zone: Lessons for Allied Planners"


@pytest.fixture
def api(db, session_factory, settings, fixture_bytes):
    seed_taxonomy(db)
    seed_glossary(db)
    db.add(User(email="editor@example.org", name="محرر", password_hash=hash_password("secret-pass"), role="admin"))
    db.commit()
    llm = FakeLLM(demo_handler)
    app = create_app(settings=settings, factory=session_factory, llm=llm)
    client = TestClient(app)

    def ingest(rights=RightsLevel.a, slug="example"):
        make_source(db, slug=slug, rights=rights, license="CC BY-NC 4.0" if rights == RightsLevel.a else None)
        http = PoliteClient(settings, transport=mock_transport({FEED: (200, fixture_bytes("feed.xml"))}))
        for _ in range(6):
            run_once(session_factory, llm, http, settings)
        db.expire_all()
        return db.scalar(select(Document).where(Document.title_en == GRAY))

    client.ingest = ingest
    return client


def login(api) -> dict:
    r = api.post("/api/editor/login", json={"email": "EDITOR@example.org", "password": "secret-pass"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_editor_endpoints_require_auth(api):
    assert api.get("/api/editor/queue").status_code == 401
    assert api.get("/api/editor/queue", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert api.post("/api/editor/login", json={"email": "editor@example.org", "password": "x"}).status_code == 401


def test_review_edit_publish_flow(api, db):
    doc = api.ingest()
    h = login(api)
    queue = api.get("/api/editor/queue", headers=h).json()
    assert doc.id in [row["id"] for row in queue["items"]]
    assert api.get(f"/api/articles/{doc.id}").status_code == 404  # not public before approval

    new_text = "فقرة معدّلة من المحرر عن الردع بالمنع في المنطقة الرمادية."
    r = api.patch(f"/api/editor/items/{doc.id}", headers=h, json={"paragraphs": {"0": new_text},
                                                                  "summary": {"dek_ar": "سطر تعريفي جديد"}})
    assert r.status_code == 200
    assert r.json()["translation"]["paragraphs_ar"][0] == new_text

    r = api.post(f"/api/editor/items/{doc.id}/publish", headers=h)
    assert r.status_code == 200 and r.json()["stage"] == "published"

    public = api.get(f"/api/articles/{doc.id}").json()
    assert public["publish_level"] == "full" and public["human_reviewed"] is True
    assert public["body"][0] == {"en": doc.paragraphs_en[0], "ar": new_text}
    assert public["dek_ar"] == "سطر تعريفي جديد"
    assert public["license"] == "CC BY-NC 4.0"
    assert {"en": "gray zone", "ar": "المنطقة الرمادية", "definition_ar": ""} in public["glossary"]
    listing = api.get("/api/articles", params={"topic": "deterrence"}).json()
    assert [a["id"] for a in listing["items"]] == [doc.id]
    assert api.get("/api/articles", params={"topic": "cyber"}).json()["total"] == 0

    actions = db.scalars(select(AuditLog.action).where(AuditLog.entity_id == doc.id)).all()
    assert "edit" in actions and "publish" in actions

    # Takedown removes it from the public site at once.
    api.post(f"/api/editor/items/{doc.id}/unpublish", headers=h, json={"reason": "طلب المصدر"})
    assert api.get(f"/api/articles/{doc.id}").status_code == 404


def test_summary_only_source_never_exposes_body(api, db):
    doc = api.ingest(rights=RightsLevel.c)
    h = login(api)
    # Even if body text somehow exists in the database, the public API must not serve it.
    doc.translation.paragraphs_ar = ["نص لا يجوز نشره"] * len(doc.paragraphs_en)
    db.commit()
    assert api.patch(f"/api/editor/items/{doc.id}", headers=h, json={"publish_level": "full"}).status_code == 403
    api.post(f"/api/editor/items/{doc.id}/publish", headers=h)
    public = api.get(f"/api/articles/{doc.id}").json()
    assert public["publish_level"] == "summary"
    assert public["body"] is None and public["license"] is None
    assert public["summary"]["thesis_ar"]
    assert "ملخص تحليلي" in public["rights_note"]


@pytest.mark.parametrize("query", ["الردع بالمنع", "الرَّدْع", "ردع", "المنطقه الرماديه", "سلم التصعيد", "Jane Analyst"])
def test_arabic_search_handles_variants(api, query):
    doc = api.ingest()
    api.post(f"/api/editor/items/{doc.id}/publish", headers=login(api))
    result = api.get("/api/search", params={"q": query}).json()
    assert [a["id"] for a in result["items"]] == [doc.id], query


def test_search_does_not_match_unrelated(api):
    doc = api.ingest()
    api.post(f"/api/editor/items/{doc.id}/publish", headers=login(api))
    assert api.get("/api/search", params={"q": "الصواريخ فرط الصوتية"}).json()["total"] == 0


def test_feedback_and_glossary(api):
    doc = api.ingest()
    h = login(api)
    assert api.post("/api/feedback", json={"document_id": doc.id, "message": "خطأ"}).status_code == 404  # unpublished
    api.post(f"/api/editor/items/{doc.id}/publish", headers=h)
    assert api.post("/api/feedback", json={"document_id": doc.id, "paragraph_index": 2,
                                           "message": "ترجمة غير دقيقة"}).status_code == 201
    fb = api.get("/api/editor/feedback", headers=h).json()
    assert fb[0]["paragraph_index"] == 2
    api.post(f"/api/editor/feedback/{fb[0]['id']}/resolve", headers=h)
    assert api.get("/api/editor/feedback", headers=h).json() == []

    proposed = api.get("/api/editor/glossary", params={"status": "proposed"}, headers=h).json()
    assert {"attribution", "fait accompli"} <= {t["term_en"] for t in proposed}
    r = api.post("/api/editor/glossary", headers=h, json={"term_en": "attribution", "term_ar": "إسناد المسؤولية",
                                                          "variants_ar": ["تحديد المسؤولية"]})
    assert r.json()["status"] == "approved"
    assert any(t["en"] == "attribution" for t in api.get("/api/glossary", params={"q": "اسناد"}).json())


def test_source_rights_change_requires_admin_and_evidence(api, db):
    h = login(api)
    make_source(db, slug="newsrc", rights=RightsLevel.c)
    r = api.patch("/api/editor/sources/newsrc", headers=h, json={"rights_level": "b"})
    assert r.status_code == 400
    r = api.patch("/api/editor/sources/newsrc", headers=h,
                  json={"rights_level": "b", "rights_evidence": "Email from editor, 2026-11-20"})
    assert r.status_code == 200 and r.json()["rights_level"] == "b"
    db.expire_all()
    assert db.scalar(select(Source).where(Source.slug == "newsrc")).rights_level == RightsLevel.b

    db.scalar(select(User)).role = "editor"
    db.commit()
    assert api.patch("/api/editor/sources/newsrc", headers=h, json={"is_active": False}).status_code == 403


def test_stats_and_retranslate(api):
    doc = api.ingest()
    h = login(api)
    stats = api.get("/api/editor/stats", headers=h).json()
    assert stats["stages"]["review"] >= 1 and stats["spent_today_usd"] > 0
    r = api.post(f"/api/editor/items/{doc.id}/paragraphs/1/retranslate", headers=h)
    assert r.status_code == 200 and "2024" in r.json()["ar"]
    assert api.get("/api/health").json() == {"ok": True}
