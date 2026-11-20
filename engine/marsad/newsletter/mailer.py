"""Outgoing email over SMTP (works with Postmark, SES, Resend, Mailgun...). FakeMailer for tests and demos."""

import logging
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

from marsad.config import Settings

log = logging.getLogger(__name__)


class MailError(Exception):
    pass


class Mailer(Protocol):
    def send(self, to: str, subject: str, html: str, text: str, headers: dict[str, str] | None = None) -> None: ...


def mask(email: str) -> str:
    user, _, domain = email.partition("@")
    return f"{user[:2]}***@{domain}"


class SmtpMailer:
    def __init__(self, settings: Settings):
        self.s = settings

    def send(self, to, subject, html, text, headers=None):
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.s.smtp_from, to, subject
        msg["Message-ID"] = make_msgid(domain=self.s.smtp_from.rpartition("@")[2].strip("> ") or None)
        for k, v in (headers or {}).items():
            msg[k] = v
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        try:
            with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30) as smtp:
                if self.s.smtp_starttls:
                    smtp.starttls()
                if self.s.smtp_user:
                    smtp.login(self.s.smtp_user, self.s.smtp_password)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise MailError(f"{type(exc).__name__}: {exc}") from exc
        log.info("mail sent to %s: %s", mask(to), subject)


@dataclass
class FakeMailer:
    sent: list[dict] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    def send(self, to, subject, html, text, headers=None):
        if to in self.fail_for:
            raise MailError("simulated failure")
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text, "headers": headers or {}})


def make_mailer(settings: Settings) -> Mailer | None:
    backend = settings.mail_backend
    if backend == "auto":
        backend = "smtp" if settings.smtp_host else "none"
    if backend == "smtp":
        return SmtpMailer(settings)
    if backend == "fake":
        return FakeMailer()
    return None
