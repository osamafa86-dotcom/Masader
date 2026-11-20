"""Thematic dossiers: editor-curated groups of items with an introduction."""

import json

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.ai import prompts, schemas
from marsad.ai.llm import LLM
from marsad.config import Settings
from marsad.models import AiUsage, DocEmbedding, Document, Dossier, DossierItem, Stage


def unique_slug(session: Session, title: str, wanted: str | None = None) -> str:
    base = slugify(wanted or title)[:100] or "dossier"
    slug, n = base, 2
    while session.scalar(select(Dossier.id).where(Dossier.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def set_items(session: Session, dossier: Dossier, items: list[dict]) -> None:
    """items: [{document_id, note_ar}] in display order. Only published documents are kept."""
    ids = [int(i["document_id"]) for i in items]
    published = set(session.scalars(select(Document.id).where(Document.id.in_(ids or [0]),
                                                              Document.stage == Stage.published)).all())
    seen: set[int] = set()
    dossier.items = []
    session.flush()
    for pos, it in enumerate(items):
        did = int(it["document_id"])
        if did in published and did not in seen:
            seen.add(did)
            dossier.items.append(DossierItem(document_id=did, position=pos, note_ar=(it.get("note_ar") or "")[:2000]))


def centroid(session: Session, dossier: Dossier) -> list[float] | None:
    vecs = [list(e.embedding) for e in session.scalars(
        select(DocEmbedding).where(DocEmbedding.document_id.in_([i.document_id for i in dossier.items] or [0]))).all()]
    if not vecs:
        return None
    return [sum(col) / len(vecs) for col in zip(*vecs)]


def draft_intro(session: Session, dossier: Dossier, llm: LLM, settings: Settings) -> str:
    items = []
    for n, it in enumerate(dossier.items, start=1):
        doc, tr = it.document, it.document.translation
        s = tr.summary or {}
        items.append({"n": n, "title_ar": tr.title_ar, "source": doc.source.name_ar,
                      "date": doc.published_at.date().isoformat() if doc.published_at else "",
                      "dek_ar": s.get("dek_ar", ""), "thesis_ar": s.get("thesis_ar", ""), "editor_note": it.note_ar})
    payload = {"title_ar": dossier.title_ar, "items": items}
    res = llm.json(task="dossier_intro", model=settings.model_summarize, system=prompts.DOSSIER_INTRO,
                   user=json.dumps(payload, ensure_ascii=False), schema=schemas.DOSSIER_INTRO, max_tokens=4000,
                   effort=settings.effort_translate)
    session.add(AiUsage(task="dossier_intro", model=res.model, input_tokens=res.input_tokens,
                        output_tokens=res.output_tokens, cost_usd=res.cost_usd))
    dossier.intro_ar, dossier.intro_is_draft = res.data["intro_ar"].strip(), True
    return dossier.intro_ar
