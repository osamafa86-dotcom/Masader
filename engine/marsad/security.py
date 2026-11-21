"""Security helpers: TOTP two-factor codes (RFC 6238), secret encryption, rate counters and login lockout."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from marsad.config import Settings
from marsad.models import LoginAttempt, RateCounter

TOTP_STEP = 30
TOTP_DIGITS = 6
LOCK_WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_ADDRESS = 20


# ---------------------------------------------------------------- TOTP
def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** TOTP_DIGITS).zfill(TOTP_DIGITS)


def totp_now(secret: str, at: float | None = None) -> str:
    return _code(secret, int((at or time.time()) // TOTP_STEP))


def verify_totp(secret: str, code: str, last_step: int | None, at: float | None = None) -> int | None:
    """Returns the matched time step (store it to refuse replays), or None. Accepts one step of clock drift."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != TOTP_DIGITS:
        return None
    now = int((at or time.time()) // TOTP_STEP)
    for step in (now - 1, now, now + 1):
        if hmac.compare_digest(_code(secret, step), code) and (last_step is None or step > last_step):
            return step
    return None


def otpauth_uri(secret: str, account: str, issuer: str) -> str:
    from urllib.parse import quote

    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_STEP}")


def qr_svg(data: str) -> str:
    import io

    import segno

    out = io.BytesIO()
    segno.make(data, error="m").save(out, kind="svg", scale=5, border=2, xmldecl=False, svgns=True)
    return out.getvalue().decode()


# ---------------------------------------------------------------- secret encryption
def _fernet(settings: Settings) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt(settings: Settings, value: str) -> str:
    return _fernet(settings).encrypt(value.encode()).decode()


def decrypt(settings: Settings, token: str) -> str | None:
    try:
        return _fernet(settings).decrypt(token.encode()).decode()
    except InvalidToken:
        return None


# ---------------------------------------------------------------- rate counters
def hit(session: Session, bucket: str, key: str, limit: int, window_seconds: int) -> bool:
    """Count one event; returns False when the limit for the current window is exceeded."""
    now = datetime.now(timezone.utc)
    window = datetime.fromtimestamp(int(now.timestamp()) // window_seconds * window_seconds, tz=timezone.utc)
    stmt = insert(RateCounter).values(bucket=bucket, key=key[:200], window_start=window, count=1)
    stmt = stmt.on_conflict_do_update(index_elements=[RateCounter.bucket, RateCounter.key, RateCounter.window_start],
                                      set_={"count": RateCounter.count + 1}).returning(RateCounter.count)
    count = session.execute(stmt).scalar_one()
    session.commit()
    return count <= limit


# ---------------------------------------------------------------- login lockout
def locked_out(session: Session, email: str, address: str) -> bool:
    since = datetime.now(timezone.utc) - LOCK_WINDOW
    by_email = session.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.email == email, LoginAttempt.success.is_(False), LoginAttempt.created_at > since))
    by_addr = session.scalar(select(func.count()).select_from(LoginAttempt).where(
        LoginAttempt.client_address == address, LoginAttempt.success.is_(False), LoginAttempt.created_at > since))
    return by_email >= MAX_FAILURES_PER_EMAIL or by_addr >= MAX_FAILURES_PER_ADDRESS


def record_attempt(session: Session, email: str, address: str, success: bool) -> None:
    session.add(LoginAttempt(email=email, client_address=address, success=success))
    session.commit()
