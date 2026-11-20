"""Dossier endpoints: public reading and editorial curation."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from marsad.api import public as pub
from marsad.api.auth import current_user
from marsad.api.deps import get_db, get_embedder, get_llm, get_settings_dep
from marsad.api.serialize import article_card, queue_row
from marsad.dossiers import centroid, draft_intro, set_items, unique_slug
from marsad.embed import embed_query
from marsad.models import AuditLog, Document, Dossier, DossierItem, User, utcnow

public = APIRouter(prefix="/api")
editor = APIRouter(prefix="/api/editor")


def _load(db: Session, **where) -> Dossier | None:
    q = select(Dossier).options(selectinload(Dossier.items).selectinload(DossierItem.document).options(*pub._LOAD))
    for k, v in where.items():
        q = q.where(getattr(Dossier, k) == v)
    return db.scalar(q)


def dossier_card(d: Dossier) -> dict:
    return {"slug": d.slug, "title_ar": d.title_ar, "item_count": len(d.items),
            "excerpt_ar": d.intro_ar[:280], "published_at": d.published_at.isoformat() if d.published_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None}


def dossier_public(d: Dossier) -> dict:
    from marsad.models import Stage

    items = [{**article_card(i.document), "note_ar": i.note_ar} for i in d.items
             if i.document.stage == Stage.published]  # a taken-down item disappears from the dossier too
    return {**dossier_card(d), "intro_ar": d.intro_ar, "items": items, "item_count": len(items)}


@public.get("/dossiers")
def list_dossiers(db: Session = Depends(get_db)):
    rows = db.scalars(select(Dossier).where(Dossier.status == "published").options(selectinload(Dossier.items))
                      .order_by(Dossier.published_at.desc())).all()
    return [dossier_card(d) for d in rows]


@public.get("/dossiers/{slug}")
def get_dossier(slug: str, db: Session = Depends(get_db)):
    d = _load(db, slug=slug)
    if d is None or d.status != "published":
        raise HTTPException(404, "الملف غير موجود")
    return dossier_public(d)


# ---------------------------------------------------------------- editor
def _editor_json(d: Dossier) -> dict:
    return {"id": d.id, "slug": d.slug, "title_ar": d.title_ar, "intro_ar": d.intro_ar, "intro_is_draft": d.intro_is_draft,
            "status": d.status, "published_at": d.published_at.isoformat() if d.published_at else None,
            "items": [{**queue_row(i.document), "note_ar": i.note_ar} for i in d.items]}


def _get(db: Session, dossier_id: int) -> Dossier:
    d = _load(db, id=dossier_id)
    if d is None:
        raise HTTPException(404, "الملف غير موجود")
    return d


@editor.get("/dossiers")
def editor_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Dossier).options(selectinload(Dossier.items)).order_by(Dossier.updated_at.desc())).all()
    return [{**dossier_card(d), "id": d.id, "status": d.status} for d in rows]


class DossierIn(BaseModel):
    title_ar: str = Field(..., min_length=3, max_length=300)
    slug: str | None = Field(None, max_length=100)


@editor.post("/dossiers", status_code=201)
def create(body: DossierIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = Dossier(title_ar=body.title_ar.strip(), slug=unique_slug(db, body.title_ar, body.slug), created_by=user.id)
    db.add(d)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="dossier_create", entity="dossier", entity_id=d.id, detail={}))
    db.commit()
    return _editor_json(_get(db, d.id))


@editor.get("/dossiers/{dossier_id}")
def editor_get(dossier_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _editor_json(_get(db, dossier_id))


class ItemIn(BaseModel):
    document_id: int
    note_ar: str = ""


class DossierPatch(BaseModel):
    title_ar: str | None = Field(None, min_length=3, max_length=300)
    intro_ar: str | None = Field(None, max_length=6000)
    items: list[ItemIn] | None = None


@editor.patch("/dossiers/{dossier_id}")
def patch(dossier_id: int, body: DossierPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, dossier_id)
    if body.title_ar is not None:
        d.title_ar = body.title_ar.strip()
    if body.intro_ar is not None:
        d.intro_ar, d.intro_is_draft = body.intro_ar.strip(), False  # saved by an editor = reviewed
    if body.items is not None:
        set_items(db, d, [i.model_dump() for i in body.items])
    d.updated_at = utcnow()
    db.add(AuditLog(user_id=user.id, action="dossier_edit", entity="dossier", entity_id=d.id,
                    detail={"fields": sorted(body.model_dump(exclude_unset=True))}))
    db.commit()
    return _editor_json(_get(db, d.id))


@editor.post("/dossiers/{dossier_id}/publish")
def publish(dossier_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, dossier_id)
    if len(d.items) < 2:
        raise HTTPException(409, "أضف مادتين على الأقل قبل النشر")
    if not d.intro_ar.strip():
        raise HTTPException(409, "اكتب مقدمة للملف قبل النشر")
    if d.intro_is_draft:
        raise HTTPException(409, "المقدمة مقترحة من النموذج: راجعها واحفظها قبل النشر")
    d.status, d.published_at = "published", d.published_at or utcnow()
    db.add(AuditLog(user_id=user.id, action="dossier_publish", entity="dossier", entity_id=d.id, detail={}))
    db.commit()
    return _editor_json(d)


@editor.post("/dossiers/{dossier_id}/unpublish")
def unpublish(dossier_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _get(db, dossier_id)
    d.status = "draft"
    db.add(AuditLog(user_id=user.id, action="dossier_unpublish", entity="dossier", entity_id=d.id, detail={}))
    db.commit()
    return _editor_json(d)


@editor.get("/dossiers/{dossier_id}/suggestions")
def suggestions(dossier_id: int, q: str | None = Query(None, max_length=200), user: User = Depends(current_user),
                db: Session = Depends(get_db), embedder=Depends(get_embedder), settings=Depends(get_settings_dep)):
    """Candidates by the editor's query and by closeness to the items already in the dossier."""
    d = _get(db, dossier_id)
    have = {i.document_id for i in d.items}
    rankings: list[list[int]] = []
    if q and len(q.strip()) >= 2:
        rankings.append(pub._keyword_ids(db, q))
        vec = embed_query(embedder, q)
        if vec is not None:
            rankings.append(pub._vector_ids(db, vec, settings.semantic_min_similarity))
    center = centroid(db, d)
    if center is not None:
        rankings.append(pub._vector_ids(db, center, settings.semantic_min_similarity))
    ids = [i for i in pub._fuse(*rankings) if i not in have][:20]
    docs = {x.id: x for x in db.scalars(select(Document).where(Document.id.in_(ids or [0]))).all()}
    return [queue_row(docs[i]) for i in ids if i in docs]


@editor.post("/dossiers/{dossier_id}/draft-intro")
def make_intro(dossier_id: int, user: User = Depends(current_user), db: Session = Depends(get_db),
               llm=Depends(get_llm), settings=Depends(get_settings_dep)):
    d = _get(db, dossier_id)
    if not d.items:
        raise HTTPException(409, "أضف مواد إلى الملف أولاً")
    draft_intro(db, d, llm, settings)
    db.commit()
    return _editor_json(d)
