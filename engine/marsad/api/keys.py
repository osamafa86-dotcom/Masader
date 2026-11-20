"""API keys for institutions: hashed storage and a per-minute rate limit counted in Postgres."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from marsad.api.deps import get_db
from marsad.models import ApiClient, ApiUsage

KEY_PREFIX = "mrsd_"


def new_key() -> tuple[str, str, str]:
    """Returns (key shown once, sha256 hash stored, short prefix for display)."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return key, hash_key(key), key[:12]


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _key_from(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def api_client(response: Response, db: Session = Depends(get_db),
               x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> ApiClient:
    key = _key_from(x_api_key, authorization)
    if not key:
        raise HTTPException(401, "API key required (X-API-Key header)", headers={"WWW-Authenticate": "Bearer"})
    client = db.scalar(select(ApiClient).where(ApiClient.key_hash == hash_key(key)))
    if client is None or not client.is_active:
        raise HTTPException(401, "invalid or revoked API key", headers={"WWW-Authenticate": "Bearer"})

    now = datetime.now(timezone.utc)
    window = now.replace(second=0, microsecond=0)
    stmt = insert(ApiUsage).values(client_id=client.id, window_start=window, count=1)
    stmt = stmt.on_conflict_do_update(index_elements=[ApiUsage.client_id, ApiUsage.window_start],
                                      set_={"count": ApiUsage.count + 1}).returning(ApiUsage.count)
    count = db.execute(stmt).scalar_one()
    if client.last_used_at is None or now - client.last_used_at > timedelta(minutes=1):
        client.last_used_at = now
    db.commit()

    reset = int((window + timedelta(minutes=1) - now).total_seconds()) + 1
    limit = client.rate_limit_per_minute
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
    response.headers["X-RateLimit-Reset"] = str(reset)
    if count > limit:
        raise HTTPException(429, f"rate limit of {limit} requests per minute exceeded",
                            headers={"Retry-After": str(reset), "X-RateLimit-Limit": str(limit),
                                     "X-RateLimit-Remaining": "0"})
    return client
