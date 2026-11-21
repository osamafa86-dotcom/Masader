"""Reader account endpoints. The website sends the reader's session token in X-Reader-Token."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad import accounts
from marsad.api import public as pub
from marsad.api.deps import get_db, get_settings_dep, limited
from marsad.api.newsletter import get_mailer
from marsad.api.serialize import article_card
from marsad.models import Document, Reader, SavedItem, Stage
from marsad.newsletter import service as nl
from marsad.newsletter.mailer import MailError

router = APIRouter(prefix="/api/account")


def current_reader(x_reader_token: str | None = Header(default=None), db: Session = Depends(get_db)) -> Reader:
    reader = accounts.reader_for(db, x_reader_token)
    if reader is None:
        raise HTTPException(401, "سجّل الدخول للمتابعة")
    return reader


class EmailIn(BaseModel):
    email: str = Field(..., max_length=320)


@router.post("/login", status_code=202, dependencies=[Depends(limited("reader_login", 10, 3600))])
def login(body: EmailIn, db: Session = Depends(get_db), mailer=Depends(get_mailer), settings=Depends(get_settings_dep)):
    email = nl.normalize_email(body.email)
    if email is None:
        raise HTTPException(422, "اكتب بريداً إلكترونياً صحيحاً")
    try:
        accounts.request_link(db, email, mailer, settings)
    except MailError:
        raise HTTPException(502, "تعذّر إرسال الرابط الآن. حاول مجدداً بعد قليل.")
    return {"ok": True, "message": "إن كان البريد صحيحاً فسيصلك رابط الدخول خلال دقائق."}


class TokenIn(BaseModel):
    token: str = Field(..., max_length=100)


@router.post("/verify")
def verify(body: TokenIn, db: Session = Depends(get_db)):
    try:
        return {"session_token": accounts.verify_link(db, body.token)}
    except accounts.LinkInvalid:
        raise HTTPException(400, "رابط الدخول غير صالح أو استُخدم من قبل أو انتهت مدته. اطلب رابطاً جديداً.")


@router.post("/logout")
def logout(x_reader_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    if x_reader_token:
        accounts.end_session(db, x_reader_token)
    return {"ok": True}


def _alerts(db: Session, reader: Reader) -> dict:
    sub = accounts.subscriber_for(db, reader)
    active = sub is not None and sub.confirmed_at is not None and sub.unsubscribed_at is None
    return {"active": active, "topics": sub.topics if sub else [], "sources": sub.sources if sub else [],
            "keywords": sub.keywords if sub else []}


@router.get("/me")
def me(reader: Reader = Depends(current_reader), db: Session = Depends(get_db)):
    saved = db.scalars(select(SavedItem.document_id).where(SavedItem.reader_id == reader.id)).all()
    return {"email": reader.email, "created_at": reader.created_at.isoformat(), "saved_ids": list(saved),
            "alerts": _alerts(db, reader)}


@router.get("/library")
def library(reader: Reader = Depends(current_reader), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedItem).where(SavedItem.reader_id == reader.id).order_by(SavedItem.created_at.desc())).all()
    docs = {d.id: d for d in db.scalars(pub.published().where(Document.id.in_([r.document_id for r in rows] or [0]))).unique().all()}
    out = []
    for r in rows:
        doc = docs.get(r.document_id)
        out.append({"document_id": r.document_id, "note": r.note, "saved_at": r.created_at.isoformat(),
                    "available": doc is not None, "article": article_card(doc) if doc else None})
    return out


class NoteIn(BaseModel):
    note: str = Field("", max_length=2000)


@router.put("/library/{doc_id}")
def save_item(doc_id: int, body: NoteIn, reader: Reader = Depends(current_reader), db: Session = Depends(get_db)):
    if db.scalar(select(Document.id).where(Document.id == doc_id, Document.stage == Stage.published)) is None:
        raise HTTPException(404, "المادة غير موجودة")
    row = db.get(SavedItem, (reader.id, doc_id)) or SavedItem(reader_id=reader.id, document_id=doc_id)
    row.note = body.note.strip()
    db.add(row)
    db.commit()
    return {"saved": True}


@router.delete("/library/{doc_id}")
def unsave_item(doc_id: int, reader: Reader = Depends(current_reader), db: Session = Depends(get_db)):
    row = db.get(SavedItem, (reader.id, doc_id))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"saved": False}


class AlertsIn(BaseModel):
    active: bool
    topics: list[str] = []
    sources: list[str] = []
    keywords: list[str] = []


@router.put("/alerts")
def alerts(body: AlertsIn, reader: Reader = Depends(current_reader), db: Session = Depends(get_db)):
    accounts.set_alerts(db, reader, body.active, nl.clean_prefs(body.topics, body.sources, body.keywords))
    return _alerts(db, reader)


@router.delete("")
def delete(reader: Reader = Depends(current_reader), db: Session = Depends(get_db)):
    accounts.delete_account(db, reader)
    return {"deleted": True}
