import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.demo import load_demo
from marsad.embed import EmbedError, FakeEmbedder, VoyageEmbedder, embed_pending
from marsad.models import EMBED_DIM, DocEmbedding, Document
from marsad.seed import seed_all

GRAY = "Deterrence in the Gray Zone: Lessons for Allied Planners"


class BrokenEmbedder:
    model = "broken"

    def embed(self, texts, kind):
        raise EmbedError("provider down")


def test_voyage_request_shape():
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": [0.2] * EMBED_DIM},
                                                  {"index": 0, "embedding": [0.1] * EMBED_DIM}]})

    v = VoyageEmbedder("key-123", transport=httpx.MockTransport(handler))
    out = v.embed(["a", "b"], "document")
    assert out[0][0] == 0.1 and out[1][0] == 0.2  # re-ordered by index
    assert seen["auth"] == "Bearer key-123"
    assert seen["body"] == {"input": ["a", "b"], "model": "voyage-3.5", "input_type": "document",
                            "output_dimension": EMBED_DIM}
    failing = VoyageEmbedder("k", transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(EmbedError):
        failing.embed(["a"], "query")


@pytest.fixture
def demo(db, settings, session_factory):
    seed_all(db)
    load_demo(db, settings)
    return db


def api_with(session_factory, settings, embedder):
    return TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                 embedder=embedder))


def test_embed_pending_is_incremental(demo):
    emb = FakeEmbedder()
    assert embed_pending(demo, emb) == 6
    assert embed_pending(demo, emb) == 0
    assert demo.scalar(select(func.count()).select_from(DocEmbedding)) == 6
    assert embed_pending(demo, BrokenEmbedder()) == 0  # model changed but provider down: nothing breaks


def test_related_falls_back_to_tags_without_vectors(demo, session_factory, settings):
    api = api_with(session_factory, settings, None)
    gray = demo.scalar(select(Document).where(Document.title_en == GRAY))
    r = api.get(f"/api/articles/{gray.id}/related").json()
    assert r["basis"] == "tags"
    titles = [a["title_en"] for a in r["items"]]
    assert titles[0] == "Naval Logistics After the Pacific Exercises"  # shares two tags: naval, indo-pacific
    assert "La dissuasion française à l'épreuve de la haute intensité" in titles  # shares one: deterrence


def test_related_and_semantic_search_with_vectors(demo, session_factory, settings):
    settings.semantic_min_similarity = 0.05
    embed_pending(demo, FakeEmbedder())
    api = api_with(session_factory, settings, FakeEmbedder())
    gray = demo.scalar(select(Document).where(Document.title_en == GRAY))
    r = api.get(f"/api/articles/{gray.id}/related").json()
    assert r["basis"] == "semantic" and gray.id not in [a["id"] for a in r["items"]]

    res = api.get("/api/search", params={"q": "الردع في المنطقة الرمادية", "mode": "semantic"}).json()
    assert res["mode"] == "semantic" and res["items"][0]["id"] == gray.id


def test_search_survives_embedding_outage(demo, session_factory, settings):
    api = api_with(session_factory, settings, BrokenEmbedder())
    res = api.get("/api/search", params={"q": "ردع", "mode": "semantic"}).json()
    assert res["mode"] == "keyword" and res["total"] == 2
    res = api.get("/api/search", params={"q": "ردع", "mode": "semantic"})
    assert res.status_code == 200
