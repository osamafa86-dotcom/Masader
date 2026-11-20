"""Public read API used by the website."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from marsad.api.deps import get_db, get_embedder, get_settings_dep
from marsad.embed import embed_query
from marsad.api.serialize import article_card, article_detail, source_brief
from marsad.arabic import loose_form, normalize_ar
from marsad.models import (
    Author,
    DocEmbedding,
    Document,
    DocumentAuthor,
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
         selectinload(Document.tags).selectinload(DocumentTag.term),
         selectinload(Document.author_links).selectinload(DocumentAuthor.author))


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
def get_article(doc_id: int, db: Session = Depends(get_db), settings=Depends(get_settings_dep)):
    doc = db.scalar(published().where(Document.id == doc_id))
    if doc is None:
        raise HTTPException(404, "المادة غير موجودة")
    glossary = db.scalars(select(GlossaryTerm).where(GlossaryTerm.status == "approved")).all()
    return article_detail(doc, glossary, settings.site_name, settings.site_url)


@router.get("/authors/{slug}")
def get_author(slug: str, page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    author = db.scalar(select(Author).where(Author.slug == slug))
    if author is None:
        raise HTTPException(404, "الكاتب غير موجود")
    q = published().where(Document.author_links.any(DocumentAuthor.author_id == author.id)) \
        .order_by(Document.published_at.desc().nulls_last())
    listing = _page(db, q, page, 20)
    sources = sorted({a["source"]["name_ar"] for a in listing["items"]})
    return {"name": author.name, "name_ar": author.name_ar, "affiliation": author.affiliation, "slug": author.slug,
            "sources": sources, **listing}


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


def _issue_key():
    return (Document.meta["volume"].astext, Document.meta["issue"].astext)


@router.get("/sources/{slug}/issues")
def list_issues(slug: str, db: Session = Depends(get_db)):
    """Journal issues that have at least one published item, newest first."""
    vol, iss = _issue_key()
    rows = db.execute(
        select(vol, iss, func.count(), func.max(Document.published_at))
        .join(Translation).join(Source, Source.id == Document.source_id)
        .where(Source.slug == slug, Document.stage == Stage.published, vol.is_not(None), iss.is_not(None))
        .group_by(vol, iss)
    ).all()
    def num(v):
        return int(v) if str(v).isdigit() else 0
    rows = sorted(rows, key=lambda r: (num(r[0]), num(r[1])), reverse=True)
    return [{"volume": r[0], "issue": r[1], "count": r[2], "latest": r[3].isoformat() if r[3] else None} for r in rows]


@router.get("/sources/{slug}/issues/{volume}/{issue}")
def get_issue(slug: str, volume: str, issue: str, db: Session = Depends(get_db)):
    vol, iss = _issue_key()
    docs = db.scalars(published().join(Source, Source.id == Document.source_id)
                      .where(Source.slug == slug, vol == volume, iss == issue)).unique().all()
    if not docs:
        raise HTTPException(404, "العدد غير موجود")
    def page(d):
        p = (d.meta or {}).get("start_page", "")
        return int(p) if str(p).isdigit() else 10**6
    return {"volume": volume, "issue": issue, "items": [article_card(d) for d in sorted(docs, key=page)]}


@router.get("/topics")
def list_topics(db: Session = Depends(get_db)):
    counts = dict(db.execute(
        select(DocumentTag.term_id, func.count()).join(Document).where(Document.stage == Stage.published)
        .group_by(DocumentTag.term_id)).all())
    out: dict[str, list] = {"topic": [], "region": [], "doc_type": []}
    for t in db.scalars(select(TaxonomyTerm).order_by(TaxonomyTerm.id)).all():
        out[t.kind].append({"slug": t.slug, "name_ar": t.name_ar, "name_en": t.name_en, "count": counts.get(t.id, 0)})
    return out


RRF_K = 60
CANDIDATES = 60


def _keyword_ids(db: Session, q: str) -> list[int]:
    # The index holds normalised and article-stripped forms; the stripped form of the query matches both.
    tsq = func.plainto_tsquery("simple", loose_form(q))
    return list(db.scalars(
        select(Document.id).join(Translation).where(Document.stage == Stage.published,
                                                    Translation.search_vector.op("@@")(tsq))
        .order_by(func.ts_rank(Translation.search_vector, tsq).desc(), Translation.published_at.desc())
        .limit(CANDIDATES)).all())


def _vector_ids(db: Session, vec: list[float], min_similarity: float, exclude: int | None = None,
                limit: int = CANDIDATES) -> list[int]:
    distance = DocEmbedding.embedding.cosine_distance(vec)
    q = (select(DocEmbedding.document_id).join(Document, Document.id == DocEmbedding.document_id)
         .where(Document.stage == Stage.published, distance <= 1 - min_similarity).order_by(distance).limit(limit))
    if exclude is not None:
        q = q.where(DocEmbedding.document_id != exclude)
    return list(db.scalars(q).all())


def _fuse(*rankings: list[int]) -> list[int]:
    """Reciprocal rank fusion: robust way to merge keyword and vector rankings without score calibration."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(scores, key=lambda i: -scores[i])


def _cards_in_order(db: Session, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    docs = {d.id: d for d in db.scalars(published().where(Document.id.in_(ids))).unique().all()}
    return [article_card(docs[i]) for i in ids if i in docs]


@router.get("/search")
def search(q: str = Query(..., min_length=2, max_length=200), page: int = Query(1, ge=1),
           per_page: int = Query(20, ge=1, le=50), mode: str = Query("keyword", pattern="^(keyword|semantic)$"),
           db: Session = Depends(get_db), embedder=Depends(get_embedder), settings=Depends(get_settings_dep)):
    keyword = _keyword_ids(db, q)
    used = "keyword"
    ranking = keyword
    if mode == "semantic":
        vec = embed_query(embedder, q)
        if vec is not None:
            ranking = _fuse(keyword, _vector_ids(db, vec, settings.semantic_min_similarity))
            used = "semantic"
    start = (page - 1) * per_page
    return {"items": _cards_in_order(db, ranking[start:start + per_page]), "total": len(ranking), "page": page,
            "per_page": per_page, "q": q, "mode": used}


@router.get("/articles/{doc_id}/related")
def related(doc_id: int, limit: int = Query(5, ge=1, le=12), db: Session = Depends(get_db),
            settings=Depends(get_settings_dep)):
    doc = db.scalar(published().where(Document.id == doc_id))
    if doc is None:
        raise HTTPException(404, "المادة غير موجودة")
    ids: list[int] = []
    emb = db.get(DocEmbedding, doc_id)
    if emb is not None:
        ids = _vector_ids(db, list(emb.embedding), settings.semantic_min_similarity, exclude=doc_id, limit=limit)
    if len(ids) < limit:  # fall back to (or top up with) items sharing the most topic and region tags
        term_ids = [t.term_id for t in doc.tags if t.term.kind in ("topic", "region")]
        if term_ids:
            shared = func.count(DocumentTag.term_id)
            rows = db.execute(
                select(Document.id, shared).join(DocumentTag).join(Translation)
                .where(Document.stage == Stage.published, Document.id != doc_id,
                       DocumentTag.term_id.in_(term_ids), Document.id.not_in(ids or [0]))
                .group_by(Document.id, Translation.published_at)
                .order_by(shared.desc(), Translation.published_at.desc()).limit(limit - len(ids))).all()
            ids += [r[0] for r in rows]
    return {"items": _cards_in_order(db, ids), "basis": "semantic" if emb is not None else "tags"}


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
