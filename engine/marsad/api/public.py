"""Public read API used by the website."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from marsad.api.deps import get_db
from marsad.api.serialize import article_card, article_detail, source_brief
from marsad.arabic import loose_form, normalize_ar
from marsad.models import (
    Document,
    DocumentTag,
    Feedback,
    GlossaryTerm,
    Source,
    Stage,
    TaxonomyTerm,
    Translation,
)

router = APIRouter(prefix="/api")

_LOAD = (selectinload(Document.translation), selectinload(Document.source),
         selectinload(Document.tags).selectinload(DocumentTag.term))


def published():
    return select(Document).join(Translation).where(Document.stage == Stage.published).options(*_LOAD)


def _page(db: Session, query, page: int, per_page: int) -> dict:
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.scalars(query.offset((page - 1) * per_page).limit(per_page)).unique().all()
    return {"items": [article_card(d) for d in rows], "total": total, "page": page, "per_page": per_page}


def _has_tag(kind: str, slug: str):
    return Document.tags.any(DocumentTag.term.has((TaxonomyTerm.kind == kind) & (TaxonomyTerm.slug == slug)))


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"ok": True}


@router.get("/articles")
def list_articles(topic: str | None = None, region: str | None = None, source: str | None = None,
                  doc_type: str | None = None, min_importance: int | None = Query(None, ge=1, le=5),
                  page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    q = published()
    if topic:
        q = q.where(_has_tag("topic", topic))
    if region:
        q = q.where(_has_tag("region", region))
    if doc_type:
        q = q.where(_has_tag("doc_type", doc_type))
    if source:
        q = q.where(Document.source.has(Source.slug == source))
    if min_importance:
        q = q.where(Document.importance >= min_importance)
    return _page(db, q.order_by(Translation.published_at.desc(), Document.id.desc()), page, per_page)


@router.get("/articles/{doc_id}")
def get_article(doc_id: int, db: Session = Depends(get_db)):
    doc = db.scalar(published().where(Document.id == doc_id))
    if doc is None:
        raise HTTPException(404, "المادة غير موجودة")
    glossary = db.scalars(select(GlossaryTerm).where(GlossaryTerm.status == "approved")).all()
    return article_detail(doc, glossary)


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Document.source_id, func.count()).where(Document.stage == Stage.published)
                             .group_by(Document.source_id)).all())
    rows = db.scalars(select(Source).order_by(Source.is_active.desc(), Source.name)).all()
    return [{**source_brief(s), "description_ar": s.description_ar, "is_active": s.is_active,
             "rights_level": s.rights_level.value, "license": s.license, "published_count": counts.get(s.id, 0)}
            for s in rows]


@router.get("/sources/{slug}")
def get_source(slug: str, db: Session = Depends(get_db)):
    src = db.scalar(select(Source).where(Source.slug == slug))
    if src is None:
        raise HTTPException(404, "المصدر غير موجود")
    return {**source_brief(src), "description_ar": src.description_ar, "is_active": src.is_active,
            "rights_level": src.rights_level.value, "license": src.license}


@router.get("/topics")
def list_topics(db: Session = Depends(get_db)):
    counts = dict(db.execute(
        select(DocumentTag.term_id, func.count()).join(Document).where(Document.stage == Stage.published)
        .group_by(DocumentTag.term_id)).all())
    out: dict[str, list] = {"topic": [], "region": [], "doc_type": []}
    for t in db.scalars(select(TaxonomyTerm).order_by(TaxonomyTerm.id)).all():
        out[t.kind].append({"slug": t.slug, "name_ar": t.name_ar, "name_en": t.name_en, "count": counts.get(t.id, 0)})
    return out


@router.get("/search")
def search(q: str = Query(..., min_length=2, max_length=200), page: int = Query(1, ge=1),
           per_page: int = Query(20, ge=1, le=50), db: Session = Depends(get_db)):
    # The index holds normalised and article-stripped forms; the stripped form of the query matches both.
    tsq = func.plainto_tsquery("simple", loose_form(q))
    query = published().where(Translation.search_vector.op("@@")(tsq)).order_by(
        func.ts_rank(Translation.search_vector, tsq).desc(), Translation.published_at.desc())
    return {**_page(db, query, page, per_page), "q": q}


@router.get("/glossary")
def glossary(q: str | None = Query(None, max_length=100), db: Session = Depends(get_db)):
    rows = db.scalars(select(GlossaryTerm).where(GlossaryTerm.status == "approved").order_by(GlossaryTerm.term_en)).all()
    if q:
        needle_en, needle_ar = q.lower().strip(), normalize_ar(q)
        rows = [r for r in rows if needle_en in r.term_en.lower() or needle_ar in normalize_ar(r.term_ar)
                or any(needle_ar in normalize_ar(v) for v in r.variants_ar or [])]
    return [{"en": r.term_en, "ar": r.term_ar, "variants_ar": r.variants_ar, "definition_ar": r.definition_ar,
             "domain": r.domain} for r in rows]


class FeedbackIn(BaseModel):
    document_id: int
    paragraph_index: int | None = Field(None, ge=0)
    message: str = Field(..., min_length=3, max_length=2000)


@router.post("/feedback", status_code=201)
def post_feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    doc = db.scalar(select(Document).where(Document.id == body.document_id, Document.stage == Stage.published))
    if doc is None:
        raise HTTPException(404, "المادة غير موجودة")
    db.add(Feedback(document_id=doc.id, paragraph_index=body.paragraph_index, message=body.message.strip()))
    db.commit()
    return {"ok": True}
