"""Document embeddings for semantic search and related items (pgvector).

Backends: "voyage" (Voyage AI, multilingual, needs MARSAD_VOYAGE_API_KEY), "fake" (deterministic hashing,
for tests and keyless demos), "none". "auto" picks voyage when a key is set, else none."""

import hashlib
import logging
import math
import re
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.arabic import loose_form
from marsad.config import Settings
from marsad.models import EMBED_DIM, DocEmbedding, Document, Stage, Translation

log = logging.getLogger(__name__)


class EmbedError(Exception):
    pass


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str], kind: str) -> list[list[float]]: ...


class VoyageEmbedder:
    URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, api_key: str, model: str = "voyage-3.5", timeout: float = 20.0, transport=None):
        self.model = model
        self._client = httpx.Client(timeout=timeout, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def embed(self, texts: list[str], kind: str) -> list[list[float]]:
        try:
            r = self._client.post(self.URL, json={"input": texts, "model": self.model, "input_type": kind,
                                                  "output_dimension": EMBED_DIM})
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d["index"])
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise EmbedError(f"voyage: {exc}") from exc
        return [d["embedding"] for d in data]


class FakeEmbedder:
    """Hashed bag of words. Lexical, not semantic, but deterministic and shaped like the real thing."""

    model = "fake-hash-1"

    def embed(self, texts: list[str], kind: str) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * EMBED_DIM
            for token in re.findall(r"\w{3,}", loose_form(text)):
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vec[h % EMBED_DIM] += 1.0 if (h >> 12) % 2 else -1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def make_embedder(settings: Settings) -> Embedder | None:
    backend = settings.embed_backend
    if backend == "auto":
        backend = "voyage" if settings.voyage_api_key else "none"
    if backend == "voyage":
        return VoyageEmbedder(settings.voyage_api_key, settings.embed_model)
    if backend == "fake":
        return FakeEmbedder()
    return None


def document_text(doc: Document, tr: Translation, max_words: int = 1500) -> str:
    s = tr.summary or {}
    english = [doc.title_en, doc.abstract_en or ""]
    count = 0
    for p in doc.paragraphs_en or []:
        if count > max_words:
            break
        english.append(p)
        count += len(p.split())
    arabic = [tr.title_ar, s.get("dek_ar", ""), s.get("thesis_ar", ""), " ".join(s.get("key_points_ar", []))]
    return "\n".join(x for x in english + arabic if x)


def embed_pending(session: Session, embedder: Embedder, batch: int = 32) -> int:
    """Embed published documents that have no vector (or one from another model). Returns the number embedded."""
    rows = session.execute(
        select(Document, Translation)
        .join(Translation, Translation.document_id == Document.id)
        .outerjoin(DocEmbedding, DocEmbedding.document_id == Document.id)
        .where(Document.stage == Stage.published,
               (DocEmbedding.document_id.is_(None)) | (DocEmbedding.model != embedder.model))
        .limit(batch)
    ).all()
    if not rows:
        return 0
    try:
        vectors = embedder.embed([document_text(d, t) for d, t in rows], "document")
    except EmbedError as exc:
        log.warning("embedding skipped this cycle: %s", exc)
        return 0
    for (doc, _), vec in zip(rows, vectors):
        row = session.get(DocEmbedding, doc.id) or DocEmbedding(document_id=doc.id)
        row.model, row.embedding = embedder.model, vec
        session.add(row)
    session.commit()
    return len(rows)


def embed_query(embedder: Embedder | None, q: str) -> list[float] | None:
    if embedder is None:
        return None
    try:
        return embedder.embed([q], "query")[0]
    except EmbedError as exc:
        log.warning("query embedding failed, falling back to keyword search: %s", exc)
        return None
