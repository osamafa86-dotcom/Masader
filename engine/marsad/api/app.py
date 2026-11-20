"""FastAPI application."""

import logging

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from marsad.api import dossiers_api, editor, newsletter, public, trends_api
from marsad.config import Settings, get_settings
from marsad.db import session_factory


def create_app(settings: Settings | None = None, factory: sessionmaker | None = None, llm=None,
               embedder="default", mailer="default") -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Marsad API", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = factory or session_factory()
    if llm is None:
        from marsad.worker import make_llm
        llm = make_llm(settings)
    app.state.llm = llm
    if embedder == "default":
        from marsad.embed import make_embedder
        embedder = make_embedder(settings)
    app.state.embedder = embedder
    if mailer == "default":
        from marsad.newsletter.mailer import make_mailer
        mailer = make_mailer(settings)
    app.state.mailer = mailer
    app.include_router(public.router)
    app.include_router(editor.router)
    app.include_router(newsletter.public)
    app.include_router(newsletter.editor)
    app.include_router(dossiers_api.public)
    app.include_router(dossiers_api.editor)
    app.include_router(trends_api.public)
    app.include_router(trends_api.editor)
    from marsad.api.v1 import create_v1_app
    app.mount("/v1", create_v1_app(app.state))
    return app


def app_factory() -> FastAPI:  # uvicorn --factory marsad.api.app:app_factory
    logging.basicConfig(level=logging.INFO)
    return create_app()
