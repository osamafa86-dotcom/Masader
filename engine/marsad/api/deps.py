from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings_dep(request: Request):
    return request.app.state.settings


def get_llm(request: Request):
    return request.app.state.llm


def get_embedder(request: Request):
    return request.app.state.embedder
