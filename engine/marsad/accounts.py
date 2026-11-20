"""Reader accounts: passwordless email sign-in, saved library, alerts tied to the newsletter."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from marsad.config import Settings
from marsad.models import Reader, ReaderLoginToken, ReaderSession, SavedItem, Subscriber
from marsad.newsletter import render
from marsad.newsletter.mailer import Mailer

LINK_TTL = timedelta(minutes=20)
SESSION_TTL = timedelta(days=30)
MAX_LINKS_PER_WINDOW = 3
LINK_WINDOW = timedelta(minutes=15)


class LinkInvalid(Exception):
    pass


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def now() -> datetime:
    return datetime.now(timezone.utc)


def request_link(session: Session, email: str, mailer: Mailer, settings: Settings) -> bool:
    """Send a one-time sign-in link. Returns False when throttled (the caller answers the same either way)."""
    recent = session.scalar(select(func.count()).select_from(ReaderLoginToken).where(
        ReaderLoginToken.email == email, ReaderLoginToken.created_at > now() - LINK_WINDOW))
    if recent >= MAX_LINKS_PER_WINDOW:
        return False
    token = secrets.token_urlsafe(32)
    session.add(ReaderLoginToken(token_hash=_h(token), email=email, expires_at=now() + LINK_TTL))
    session.commit()
    subject, html, text = render.login_link(settings, token)
    mailer.send(email, subject, html, text)
    return True


def verify_link(session: Session, token: str) -> str:
    """Consume a sign-in link; returns a new session token."""
    row = session.get(ReaderLoginToken, _h(token or ""))
    if row is None or row.used_at is not None or row.expires_at < now():
        raise LinkInvalid()
    row.used_at = now()
    reader = session.scalar(select(Reader).where(Reader.email == row.email))
    if reader is None:
        reader = Reader(email=row.email)
        session.add(reader)
        session.flush()
    reader.last_login_at = now()
    session_token = secrets.token_urlsafe(32)
    session.add(ReaderSession(token_hash=_h(session_token), reader_id=reader.id, expires_at=now() + SESSION_TTL))
    session.execute(delete(ReaderSession).where(ReaderSession.reader_id == reader.id, ReaderSession.expires_at < now()))
    session.commit()
    return session_token


def reader_for(session: Session, session_token: str | None) -> Reader | None:
    if not session_token:
        return None
    row = session.get(ReaderSession, _h(session_token))
    if row is None or row.expires_at < now():
        return None
    return row.reader


def end_session(session: Session, session_token: str) -> None:
    session.execute(delete(ReaderSession).where(ReaderSession.token_hash == _h(session_token)))
    session.commit()


def subscriber_for(session: Session, reader: Reader) -> Subscriber | None:
    return session.scalar(select(Subscriber).where(Subscriber.email == reader.email))


def set_alerts(session: Session, reader: Reader, active: bool, prefs: dict) -> Subscriber | None:
    """The reader proved the address by signing in, so no second confirmation is needed."""
    sub = subscriber_for(session, reader)
    if not active:
        if sub is not None and sub.unsubscribed_at is None:
            sub.unsubscribed_at = now()
        session.commit()
        return sub
    if sub is None:
        sub = Subscriber(email=reader.email, token=secrets.token_urlsafe(24))
        session.add(sub)
    sub.confirmed_at = sub.confirmed_at or now()
    sub.unsubscribed_at = None
    for k, v in prefs.items():
        setattr(sub, k, v)
    session.commit()
    return sub


def delete_account(session: Session, reader: Reader) -> None:
    """Removes the reader, sessions, saved items, sign-in links and newsletter subscription."""
    email = reader.email
    session.execute(delete(ReaderLoginToken).where(ReaderLoginToken.email == email))
    session.execute(delete(Subscriber).where(Subscriber.email == email))
    session.execute(delete(SavedItem).where(SavedItem.reader_id == reader.id))
    session.execute(delete(ReaderSession).where(ReaderSession.reader_id == reader.id))
    session.delete(reader)
    session.commit()
