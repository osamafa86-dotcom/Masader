from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.demo import load_demo
from marsad.models import Document, PageView, Stage
from marsad.seed import seed_all


def test_views_counted_without_personal_data(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler), embedder=None, mailer=None))
    ids = {d.title_en: d.id for d in db.scalars(select(Document))}
    gray, arctic = ids["Deterrence in the Gray Zone: Lessons for Allied Planners"], ids["Arctic Competition and the Alliance"]
    ua = {"x-client-ua": "Mozilla/5.0 (Macintosh) Safari/605.1"}
    for _ in range(3):
        assert api.post("/api/views", json={"document_id": gray}, headers=ua).status_code == 204
    api.post("/api/views", json={"document_id": arctic}, headers=ua)
    api.post("/api/views", json={"document_id": arctic}, headers={"x-client-ua": "Googlebot/2.1"})  # ignored
    db.get(Document, ids["Naval Logistics After the Pacific Exercises"]).stage = Stage.review
    db.commit()
    api.post("/api/views", json={"document_id": ids["Naval Logistics After the Pacific Exercises"]}, headers=ua)  # unpublished

    rows = db.scalars(select(PageView)).all()
    assert {(r.document_id, r.count) for r in rows} == {(gray, 3), (arctic, 1)}
    assert set(PageView.__table__.columns.keys()) == {"document_id", "day", "count"}  # nothing about readers
    top = api.get("/api/most-read").json()
    assert [(a["id"], a["views"]) for a in top] == [(gray, 3), (arctic, 1)]
