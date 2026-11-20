"""Subscriptions and digests."""

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from marsad.arabic import loose_form
from marsad.config import Settings
from marsad.models import (
    Digest,
    DigestDelivery,
    Document,
    DocumentTag,
    Stage,
    Subscriber,
    Translation,
)
from marsad.newsletter import render
from marsad.newsletter.mailer import Mailer, MailError, mask

log = logging.getLogger(__name__)
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")
RESEND_AFTER = timedelta(minutes=10)
DIGEST_EVERY = timedelta(days=7)
DIGEST_MAX_ITEMS = 12


def now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str | None:
    email = (email or "").strip().lower()
    return email if EMAIL.match(email) else None


def clean_prefs(topics: list[str], sources: list[str], keywords: list[str]) -> dict:
    kws = [k.strip()[:60] for k in keywords if k and k.strip()][:20]
    return {"topics": [t for t in topics if t][:30], "sources": [s for s in sources if s][:30], "keywords": kws}


def subscribe(session: Session, email: str, prefs: dict, mailer: Mailer, settings: Settings) -> None:
    """Idempotent. Same response whatever the state, so the endpoint does not reveal who is subscribed."""
    sub = session.scalar(select(Subscriber).where(Subscriber.email == email))
    if sub is None:
        sub = Subscriber(email=email, token=secrets.token_urlsafe(24), **prefs)
        session.add(sub)
    elif sub.confirmed_at and not sub.unsubscribed_at:
        return  # already active: nothing to do, nothing to send
    else:
        if sub.unsubscribed_at:  # coming back: needs a fresh confirmation
            sub.unsubscribed_at, sub.confirmed_at = None, None
        for k, v in prefs.items():
            setattr(sub, k, v)
    if sub.confirmation_sent_at and now() - sub.confirmation_sent_at < RESEND_AFTER:
        session.commit()
        return
    subject, html, text = render.confirmation(settings, sub.token)
    mailer.send(email, subject, html, text)
    sub.confirmation_sent_at = now()
    session.commit()


def by_token(session: Session, token: str) -> Subscriber | None:
    if not token or len(token) > 64:
        return None
    return session.scalar(select(Subscriber).where(Subscriber.token == token))


def confirm(session: Session, sub: Subscriber) -> None:
    if sub.confirmed_at is None:
        sub.confirmed_at = now()
    sub.unsubscribed_at = None
    session.commit()


def unsubscribe(session: Session, sub: Subscriber) -> None:
    if sub.unsubscribed_at is None:
        sub.unsubscribed_at = now()
    session.commit()


# ---------------------------------------------------------------- digests
def _period_docs(session: Session, start: datetime, end: datetime) -> list[Document]:
    return list(session.scalars(
        select(Document).join(Translation)
        .where(Document.stage == Stage.published, Translation.published_at >= start, Translation.published_at < end)
        .order_by(Document.importance.desc().nulls_last(), Translation.published_at.desc())
        .limit(DIGEST_MAX_ITEMS)).all())


def create_draft(session: Session, settings: Settings, at: datetime | None = None) -> Digest | None:
    """Draft covering everything published since the previous digest (or the last 7 days). None if empty."""
    at = at or now()
    last = session.scalar(select(Digest).order_by(Digest.period_end.desc()).limit(1))
    start = last.period_end if last is not None else at - DIGEST_EVERY
    docs = _period_docs(session, start, at)
    if not docs:
        return None
    fmt = lambda d: f"{d.day}/{d.month}/{d.year}"  # noqa: E731
    digest = Digest(period_start=start, period_end=at, status="draft", document_ids=[d.id for d in docs],
                    subject_ar=f"{settings.site_name}: أبرز ما رُصد بين {fmt(start)} و{fmt(at)}",
                    intro_ar="مختارات هذا الأسبوع من الدراسات والتحليلات الاستراتيجية، مرتبة بحسب أهميتها للباحث.")
    session.add(digest)
    session.commit()
    return digest


def ensure_weekly_draft(session: Session, settings: Settings, at: datetime | None = None) -> Digest | None:
    """Worker hook: once the previous digest period is 7 days old, prepare the next draft for the editor."""
    at = at or now()
    last = session.scalar(select(Digest).order_by(Digest.period_end.desc()).limit(1))
    if last is not None and (last.status == "draft" or at - last.period_end < DIGEST_EVERY):
        return None
    return create_draft(session, settings, at)


def matches(sub: Subscriber, doc: Document) -> bool:
    if not (sub.topics or sub.sources or sub.keywords):
        return True
    if sub.sources and doc.source.slug in sub.sources:
        return True
    if sub.topics and any(t.term.kind in ("topic", "region") and t.term.slug in sub.topics for t in doc.tags):
        return True
    if sub.keywords and doc.translation is not None:
        haystack = f"{doc.translation.search_text} {doc.title_en.lower()}"
        return any(loose_form(k) in haystack or k.lower() in haystack for k in sub.keywords)
    return False


def start_sending(session: Session, digest: Digest, user_id: int) -> int:
    if digest.status != "draft":
        raise ValueError("digest already sent or sending")
    active = session.scalars(select(Subscriber.id).where(Subscriber.confirmed_at.is_not(None),
                                                         Subscriber.unsubscribed_at.is_(None))).all()
    for sid in active:
        session.add(DigestDelivery(digest_id=digest.id, subscriber_id=sid))
    digest.status, digest.approved_by = "sending", user_id
    session.commit()
    return len(active)


def deliver_pending(session: Session, mailer: Mailer, settings: Settings, batch: int = 50) -> int:
    """Send up to `batch` pending deliveries of digests in 'sending' state. Returns emails sent."""
    sent = 0
    for digest in session.scalars(select(Digest).where(Digest.status == "sending")).all():
        docs = {d.id: d for d in session.scalars(
            select(Document).where(Document.id.in_(digest.document_ids), Document.stage == Stage.published)
            .options(selectinload(Document.tags).selectinload(DocumentTag.term),
                     selectinload(Document.translation), selectinload(Document.source))).all()}
        ordered = [docs[i] for i in digest.document_ids if i in docs]
        pending = session.scalars(select(DigestDelivery).where(DigestDelivery.digest_id == digest.id,
                                                               DigestDelivery.status == "pending")
                                  .limit(batch - sent).with_for_update(skip_locked=True)).all()
        for d in pending:
            sub = session.get(Subscriber, d.subscriber_id)
            if sub is None or sub.unsubscribed_at is not None:
                d.status = "skipped"
                continue
            items = [doc for doc in ordered if matches(sub, doc)]
            d.item_count = len(items)
            if not items:
                d.status = "skipped"  # nothing matches this reader's alerts this week: send nothing
                continue
            html, text = render.digest(settings, digest.subject_ar, digest.intro_ar, items, sub.token)
            unsub = f"{settings.site_url.rstrip('/')}/unsubscribe?token={sub.token}"
            try:
                mailer.send(sub.email, digest.subject_ar, html, text, headers={
                    "List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})
                d.status, d.sent_at = "sent", now()
                sent += 1
            except MailError as exc:
                d.status, d.error = "failed", str(exc)[:500]
                log.warning("digest %s to %s failed: %s", digest.id, mask(sub.email), exc)
        session.flush()
        left = session.scalar(select(DigestDelivery.id).where(DigestDelivery.digest_id == digest.id,
                                                              DigestDelivery.status == "pending").limit(1))
        if left is None:
            digest.status, digest.sent_at = "sent", now()
        session.commit()
        if sent >= batch:
            break
    return sent
