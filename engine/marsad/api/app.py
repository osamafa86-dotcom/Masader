"""FastAPI application."""

import logging

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from marsad.api import editor, public
from marsad.config import Settings, get_settings
from marsad.db import session_factory


def create_app(settings: Settings | None = None, factory: sessionmaker | None = None, llm=None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Marsad API", version="0.1.0")
    app.state.settings = settings
    app.state.session_factory = factory or session_factory()
    if llm is None:
        from marsad.worker import make_llm
        llm = make_llm(settings)
    app.state.llm = llm
    app.include_router(public.router)
    app.include_router(editor.router)
    return app


def app_factory() -> FastAPI:  # uvicorn --factory marsad.api.app:app_factory
    logging.basicConfig(level=logging.INFO)
    return create_app()
