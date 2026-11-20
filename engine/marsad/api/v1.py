"""Versioned public API for institutions (mounted at /v1, documented at /v1/docs)."""

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.api import public
from marsad.api.deps import get_db, get_embedder, get_settings_dep
from marsad.api.keys import api_client
from marsad.api.serialize import article_detail
from marsad.models import Document, GlossaryTerm, Source, Translation

DESCRIPTION = """
Read-only access to Marsad: Arabic analytical summaries and translations of leading strategic-studies sources.

**Authentication.** Send your key in the `X-API-Key` header (or `Authorization: Bearer`). Keys are issued by the
Marsad team. Each key has a per-minute limit; see the `X-RateLimit-*` response headers.

**Rights.** Full translated text (`body`) is returned only where the original source's licence or written permission
allows it (`publish_level = "full"`). For every other item you receive the Arabic analytical summary and a link to
the original. Keep the attribution (`source`, `authors`, `url`, `license`) when you display content.
"""

router = APIRouter(dependencies=[Depends(api_client)])


def _envelope(page: dict) -> dict:
    return {"data": page["items"], "meta": {"page": page["page"], "per_page": page["per_page"], "total": page["total"]}}


def _since(d: date | None, end: bool = False):
    if d is None:
        return None
    return datetime.combine(d, time.max if end else time.min, tzinfo=timezone.utc)


@router.get("/articles", summary="List published items, newest first")
def articles(topic: str | None = None, region: str | None = None, source: str | None = None,
             doc_type: str | None = None, language: str | None = Query(None, description="original language, e.g. en, fr"),
             since: date | None = Query(None, description="published in Marsad on or after (YYYY-MM-DD)"),
             until: date | None = None, page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=100),
             db: Session = Depends(get_db)):
    q = public.published()
    for kind, slug in (("topic", topic), ("region", region), ("doc_type", doc_type)):
        if slug:
            q = q.where(public._has_tag(kind, slug))
    if source:
        q = q.where(Document.source.has(Source.slug == source))
    if language:
        q = q.where(Document.language == language)
    if since:
        q = q.where(Translation.published_at >= _since(since))
    if until:
        q = q.where(Translation.published_at <= _since(until, end=True))
    return _envelope(public._page(db, q.order_by(Translation.published_at.desc(), Document.id.desc()), page, per_page))


@router.get("/articles/{doc_id}", summary="One item with its summary, and full text where rights allow")
def article(doc_id: int, db: Session = Depends(get_db), settings=Depends(get_settings_dep)):
    doc = db.scalar(public.published().where(Document.id == doc_id))
    if doc is None:
        raise HTTPException(404, "not found")
    glossary = db.scalars(select(GlossaryTerm).where(GlossaryTerm.status == "approved",
                                                     GlossaryTerm.lang == (doc.language or "en"))).all()
    return {"data": article_detail(doc, glossary, settings.site_name, settings.site_url)}


@router.get("/search", summary="Keyword or semantic search (Arabic or the original language)")
def search(q: str = Query(..., min_length=2, max_length=200), mode: str = Query("keyword", pattern="^(keyword|semantic)$"),
           page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=50), db: Session = Depends(get_db),
           embedder=Depends(get_embedder), settings=Depends(get_settings_dep)):
    res = public.search(q=q, page=page, per_page=per_page, mode=mode, db=db, embedder=embedder, settings=settings)
    return {**_envelope(res), "mode": res["mode"]}


@router.get("/sources", summary="Monitored sources and their rights level")
def sources(db: Session = Depends(get_db)):
    return {"data": public.list_sources(db=db)}


@router.get("/topics", summary="Topic, region and document-type taxonomy with counts")
def topics(db: Session = Depends(get_db)):
    return {"data": public.list_topics(db=db)}


@router.get("/glossary", summary="Approved Arabic terminology")
def glossary(q: str | None = Query(None, max_length=100), lang: str | None = Query(None, pattern="^[a-z]{2}$"),
             db: Session = Depends(get_db)):
    return {"data": public.glossary(q=q, lang=lang, db=db)}


@router.get("/dossiers", summary="Published thematic dossiers")
def dossiers(db: Session = Depends(get_db)):
    from marsad.api import dossiers_api

    return {"data": dossiers_api.list_dossiers(db=db)}


@router.get("/dossiers/{slug}", summary="A dossier with its editorial introduction and items")
def dossier(slug: str, db: Session = Depends(get_db)):
    from marsad.api import dossiers_api

    return {"data": dossiers_api.get_dossier(slug=slug, db=db)}


@router.get("/trends/{month}", summary="Monthly statistics across sources (YYYY-MM), with the published report")
def trends(month: str, db: Session = Depends(get_db)):
    from marsad.api import trends_api

    return {"data": trends_api.month_stats(month=month, db=db)}


def create_v1_app(parent_state) -> FastAPI:
    app = FastAPI(title="Marsad Public API", version="1.0.0", description=DESCRIPTION,
                  docs_url="/docs", redoc_url=None, openapi_url="/openapi.json")
    for attr in ("settings", "session_factory", "llm", "embedder", "mailer"):
        setattr(app.state, attr, getattr(parent_state, attr))
    app.include_router(router)
    return app
