"""Newsletter endpoints: public subscription management and editorial digests."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marsad.api.auth import current_user
from marsad.api.deps import get_db, get_settings_dep
from marsad.api.serialize import queue_row
from marsad.models import AuditLog, Digest, DigestDelivery, Document, Stage, Subscriber, User
from marsad.newsletter import service
from marsad.newsletter.mailer import MailError, mask

public = APIRouter(prefix="/api")
editor = APIRouter(prefix="/api/editor")


def get_mailer(request: Request):
    mailer = request.app.state.mailer
    if mailer is None:
        raise HTTPException(503, "النشرة البريدية غير مفعّلة بعد")
    return mailer


class SubscribeIn(BaseModel):
    email: str = Field(..., max_length=320)
    topics: list[str] = []
    sources: list[str] = []
    keywords: list[str] = []


GENERIC = {"ok": True, "message": "إن كان البريد صحيحاً فستصلك رسالة لتأكيد الاشتراك خلال دقائق."}


@public.post("/subscribe", status_code=202)
def subscribe(body: SubscribeIn, db: Session = Depends(get_db), mailer=Depends(get_mailer),
              settings=Depends(get_settings_dep)):
    email = service.normalize_email(body.email)
    if email is None:
        raise HTTPException(422, "اكتب بريداً إلكترونياً صحيحاً")
    try:
        service.subscribe(db, email, service.clean_prefs(body.topics, body.sources, body.keywords), mailer, settings)
    except MailError:
        raise HTTPException(502, "تعذّر إرسال رسالة التأكيد الآن. حاول مجدداً بعد قليل.")
    return GENERIC


class TokenIn(BaseModel):
    token: str = Field(..., max_length=64)


def _sub(db: Session, token: str) -> Subscriber:
    sub = service.by_token(db, token)
    if sub is None:
        raise HTTPException(404, "الرابط غير صالح أو منتهٍ")
    return sub


def _prefs(sub: Subscriber) -> dict:
    return {"email": mask(sub.email), "confirmed": sub.confirmed_at is not None,
            "active": sub.confirmed_at is not None and sub.unsubscribed_at is None,
            "topics": sub.topics, "sources": sub.sources, "keywords": sub.keywords}


@public.post("/subscribe/confirm")
def confirm(body: TokenIn, db: Session = Depends(get_db)):
    sub = _sub(db, body.token)
    service.confirm(db, sub)
    return _prefs(sub)


@public.get("/subscription/{token}")
def get_subscription(token: str, db: Session = Depends(get_db)):
    return _prefs(_sub(db, token))


class PrefsIn(BaseModel):
    topics: list[str] = []
    sources: list[str] = []
    keywords: list[str] = []


@public.put("/subscription/{token}")
def update_subscription(token: str, body: PrefsIn, db: Session = Depends(get_db)):
    sub = _sub(db, token)
    for k, v in service.clean_prefs(body.topics, body.sources, body.keywords).items():
        setattr(sub, k, v)
    db.commit()
    return _prefs(sub)


@public.post("/unsubscribe")
def unsubscribe(body: TokenIn, db: Session = Depends(get_db)):
    sub = _sub(db, body.token)
    service.unsubscribe(db, sub)
    return _prefs(sub)


# ---------------------------------------------------------------- editor
def _digest_json(db: Session, d: Digest, with_items: bool = False) -> dict:
    counts = dict(db.execute(select(DigestDelivery.status, func.count()).where(DigestDelivery.digest_id == d.id)
                             .group_by(DigestDelivery.status)).all())
    out = {"id": d.id, "status": d.status, "subject_ar": d.subject_ar, "intro_ar": d.intro_ar,
           "period_start": d.period_start.isoformat(), "period_end": d.period_end.isoformat(),
           "document_ids": d.document_ids, "sent_at": d.sent_at.isoformat() if d.sent_at else None,
           "deliveries": counts}
    if with_items:
        docs = {x.id: x for x in db.scalars(select(Document).where(Document.id.in_(d.document_ids or [0]))).all()}
        out["items"] = [queue_row(docs[i]) for i in d.document_ids if i in docs]
    return out


@editor.get("/digests")
def list_digests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    active = db.scalar(select(func.count()).select_from(Subscriber).where(Subscriber.confirmed_at.is_not(None),
                                                                          Subscriber.unsubscribed_at.is_(None)))
    rows = db.scalars(select(Digest).order_by(Digest.period_end.desc()).limit(30)).all()
    return {"active_subscribers": active, "digests": [_digest_json(db, d) for d in rows]}


@editor.post("/digests", status_code=201)
def create_digest(user: User = Depends(current_user), db: Session = Depends(get_db), settings=Depends(get_settings_dep)):
    """Create this week's draft now instead of waiting for the worker."""
    last = db.scalar(select(Digest).order_by(Digest.period_end.desc()).limit(1))
    if last is not None and last.status == "draft":
        raise HTTPException(409, "توجد مسودة لم تُرسل بعد")
    digest = service.create_draft(db, settings)
    if digest is None:
        raise HTTPException(409, "لا توجد مواد منشورة جديدة منذ آخر نشرة")
    return _digest_json(db, digest, with_items=True)


def _digest(db: Session, digest_id: int) -> Digest:
    d = db.get(Digest, digest_id)
    if d is None:
        raise HTTPException(404, "النشرة غير موجودة")
    return d


@editor.get("/digests/{digest_id}")
def get_digest(digest_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _digest_json(db, _digest(db, digest_id), with_items=True)


class DigestPatch(BaseModel):
    subject_ar: str | None = Field(None, max_length=300)
    intro_ar: str | None = Field(None, max_length=3000)
    document_ids: list[int] | None = None


@editor.patch("/digests/{digest_id}")
def patch_digest(digest_id: int, body: DigestPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _digest(db, digest_id)
    if d.status != "draft":
        raise HTTPException(409, "لا يمكن تعديل نشرة أُرسلت")
    if body.subject_ar is not None:
        d.subject_ar = body.subject_ar
    if body.intro_ar is not None:
        d.intro_ar = body.intro_ar
    if body.document_ids is not None:
        published = set(db.scalars(select(Document.id).where(Document.id.in_(body.document_ids or [0]),
                                                             Document.stage == Stage.published)).all())
        d.document_ids = [i for i in body.document_ids if i in published]
    db.commit()
    return _digest_json(db, d, with_items=True)


@editor.post("/digests/{digest_id}/send")
def send_digest(digest_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _digest(db, digest_id)
    if not d.document_ids:
        raise HTTPException(409, "النشرة فارغة")
    try:
        recipients = service.start_sending(db, d, user.id)
    except ValueError:
        raise HTTPException(409, "أُرسلت هذه النشرة من قبل")
    db.add(AuditLog(user_id=user.id, action="digest_send", entity="digest", entity_id=d.id,
                    detail={"recipients": recipients}))
    db.commit()
    return _digest_json(db, d)
