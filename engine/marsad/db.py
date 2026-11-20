"""Database engine and session factory."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from marsad.config import get_settings


def make_engine(url: str | None = None):
    return create_engine(url or get_settings().database_url, pool_pre_ping=True, future=True)


_engine = None
_factory: sessionmaker[Session] | None = None


def session_factory() -> sessionmaker[Session]:
    global _engine, _factory
    if _factory is None:
        _engine = make_engine()
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
