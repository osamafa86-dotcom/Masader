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


def client_address(request: Request) -> str:
    """The reader's address as forwarded by the website (the engine API itself is not public)."""
    forwarded = request.headers.get("x-client-ip") or request.headers.get("x-forwarded-for", "")
    addr = forwarded.split(",")[0].strip()
    return (addr or (request.client.host if request.client else "unknown"))[:64]


def limited(bucket: str, limit: int, window_seconds: int):
    """Dependency factory: per-address rate limit for a public form."""
    from fastapi import Depends, HTTPException

    from marsad.security import hit

    def check(request: Request, db=Depends(get_db)):
        if not hit(db, bucket, client_address(request), limit, window_seconds):
            raise HTTPException(429, "طلبات كثيرة من عنوانك. حاول مجدداً بعد قليل.",
                                headers={"Retry-After": str(window_seconds)})
    return check
