import os

os.environ.setdefault("MARSAD_DATABASE_URL", "postgresql+psycopg://marsad:marsad@localhost:5432/marsad_test")
os.environ.setdefault("MARSAD_PER_HOST_DELAY_S", "0")
os.environ.setdefault("MARSAD_LLM_BACKEND", "fake")

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from marsad.config import get_settings
from marsad.db import make_engine
from marsad.models import Base

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def engine():
    eng = make_engine(get_settings().database_url)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    s = session_factory()
    yield s
    s.close()


@pytest.fixture
def settings(tmp_path):
    s = get_settings().model_copy()
    s.storage_dir = str(tmp_path / "storage")
    return s


@pytest.fixture
def fixture_bytes():
    return lambda name: (FIXTURES / name).read_bytes()
