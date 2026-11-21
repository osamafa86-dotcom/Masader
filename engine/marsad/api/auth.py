"""Password hashing (stdlib scrypt) and bearer-token sessions for editors."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from marsad.api.deps import get_db, get_settings_dep
from marsad.models import User, UserSession

SESSION_DAYS = 14
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        candidate = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now))
    db.add(UserSession(token_hash=_token_hash(token), user_id=user.id, expires_at=now + timedelta(days=SESSION_DAYS)))
    return token


def end_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))


def bearer(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "مطلوب تسجيل الدخول")
    return authorization[7:].strip()


TWO_FACTOR_EXEMPT = ("/api/editor/me", "/api/editor/logout", "/api/editor/2fa")


def current_user(request: Request, token: str = Depends(bearer), db: Session = Depends(get_db),
                 settings=Depends(get_settings_dep)) -> User:
    row = db.scalar(select(UserSession).where(UserSession.token_hash == _token_hash(token)))
    if row is None or row.expires_at < datetime.now(timezone.utc) or not row.user.is_active:
        raise HTTPException(401, "انتهت الجلسة، يرجى تسجيل الدخول مجدداً")
    if settings.require_editor_2fa and not row.user.totp_enabled and \
            not request.url.path.startswith(TWO_FACTOR_EXEMPT):
        raise HTTPException(403, "فعّل التحقق بخطوتين من صفحة «الأمان» قبل المتابعة")
    return row.user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(403, "هذا الإجراء متاح للمدير فقط")
    return user
