"""Worker heartbeat, health checks and email alerts for the people running the site."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marsad.config import Settings
from marsad.models import Digest, Document, RawItem, Source, Stage, SystemState
from marsad.newsletter.mailer import MailError, Mailer
from marsad.pipeline import spent_today

log = logging.getLogger(__name__)
HEARTBEAT = "worker_heartbeat"
ALERT_EVERY = timedelta(hours=12)


def now() -> datetime:
    return datetime.now(timezone.utc)


def _state(session: Session, key: str) -> SystemState | None:
    return session.get(SystemState, key)


def heartbeat(session: Session, counts: dict) -> None:
    row = _state(session, HEARTBEAT) or SystemState(key=HEARTBEAT)
    row.value, row.updated_at = {k: v for k, v in counts.items() if isinstance(v, (int, float))}, now()
    session.add(row)
    session.commit()


def worker_status(session: Session, settings: Settings) -> dict:
    row = _state(session, HEARTBEAT)
    last = row.updated_at if row else None
    stale = last is None or now() - last > timedelta(minutes=settings.worker_stale_minutes)
    return {"last_seen": last.isoformat() if last else None, "stale": stale, "last_cycle": row.value if row else {}}


def find_problems(session: Session, settings: Settings) -> list[tuple[str, str]]:
    """Returns (alert key, Arabic description) for every condition that needs a human."""
    problems: list[tuple[str, str]] = []
    day_ago, t = now() - timedelta(hours=24), now()
    for src in session.scalars(select(Source).where(Source.is_active, Source.fetch_method != "none")).all():
        if src.last_error and (src.last_success_at is None or src.last_success_at < day_ago) and src.last_fetched_at:
            problems.append((f"source:{src.slug}", f"تعذّر رصد المصدر «{src.name_ar}» منذ أكثر من يوم: {src.last_error[:200]}"))
    active = session.scalar(select(func.count()).select_from(Source).where(Source.is_active, Source.fetch_method != "none"))
    newest = session.scalar(select(func.max(RawItem.discovered_at)))
    if active and newest is not None and t - newest > timedelta(hours=48):
        problems.append(("no_new_items", "لم تُرصد أي مادة جديدة من كل المصادر منذ أكثر من 48 ساعة."))
    spent = spent_today(session)
    if settings.daily_budget_usd and spent >= 0.8 * settings.daily_budget_usd:
        problems.append((f"budget:{t.date()}", f"بلغ إنفاق اليوم {spent:.2f}$ من حد {settings.daily_budget_usd:.2f}$."))
    failed = session.scalar(select(func.count()).select_from(Document).where(Document.stage == Stage.failed,
                                                                             Document.updated_at > day_ago))
    if failed >= 5:
        problems.append((f"failures:{t.date()}", f"تعثّرت {failed} مواد خلال آخر 24 ساعة. راجع قائمة «المتعثرة»."))
    for d in session.scalars(select(Digest).where(Digest.status == "sending")).all():
        if t - d.period_end > timedelta(hours=6) and (d.sent_at is None):
            problems.append((f"digest:{d.id}", f"النشرة «{d.subject_ar}» ما زالت قيد الإرسال منذ ساعات."))
    status = worker_status(session, settings)
    if status["stale"] and status["last_seen"]:
        problems.append(("worker_stale", f"آخر دورة للعامل كانت في {status['last_seen']}."))
    return problems


def send_alerts(session: Session, mailer: Mailer | None, settings: Settings) -> int:
    recipients = [e.strip() for e in settings.alert_emails.split(",") if e.strip()]
    problems = find_problems(session, settings)
    due = []
    for key, text in problems:
        row = _state(session, f"alert:{key}")
        if row is None or now() - row.updated_at > ALERT_EVERY:
            due.append((key, text))
    if not due:
        return 0
    for key, text in due:
        log.warning("alert %s: %s", key, text)
    if mailer is None or not recipients:
        return 0
    body_text = "\n".join(f"- {text}" for _, text in due)
    html = "<div dir='rtl' style='font-family:Tahoma,Arial'><ul>" + "".join(f"<li>{text}</li>" for _, text in due) + "</ul></div>"
    try:
        for to in recipients:
            mailer.send(to, f"[{settings.site_name}] تنبيه تشغيلي ({len(due)})", html, body_text)
    except MailError as exc:
        log.warning("alert email failed: %s", exc)
        return 0
    for key, _ in due:
        row = _state(session, f"alert:{key}") or SystemState(key=f"alert:{key}")
        row.value, row.updated_at = {"sent": True}, now()
        session.add(row)
    session.commit()
    return len(due)


def init_sentry(settings: Settings, component: str) -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        log.warning("MARSAD_SENTRY_DSN is set but sentry-sdk is not installed (pip install 'marsad[sentry]')")
        return
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.0, send_default_pii=False,
                    server_name=component)
