"""Editorial API: review queue, edits, publishing decisions, glossary and source rights."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from marsad.ai.tasks import translate_one
from marsad.api.auth import admin_user, bearer, create_session, current_user, end_session, verify_password
from marsad.api.deps import client_address, get_db, get_llm, get_settings_dep
from marsad.api.serialize import editor_item, queue_row
from marsad.models import (
    AuditLog,
    Document,
    DocumentTag,
    Feedback,
    GlossaryTerm,
    PublishLevel,
    RightsLevel,
    Source,
    Stage,
    User,
)
from marsad.pipeline import build_search_text, doc_input, load_terms, publish, record_usage, spent_today

router = APIRouter(prefix="/api/editor")

_LOAD = (selectinload(Document.translation), selectinload(Document.source),
         selectinload(Document.tags).selectinload(DocumentTag.term), selectinload(Document.author_links))


def _doc(db: Session, doc_id: int) -> Document:
    doc = db.scalar(select(Document).where(Document.id == doc_id).options(*_LOAD))
    if doc is None:
        raise HTTPException(404, "المادة غير موجودة")
    return doc


def _audit(db: Session, user: User, action: str, entity: str, entity_id: int | None, **detail) -> None:
    db.add(AuditLog(user_id=user.id, action=action, entity=entity, entity_id=entity_id, detail=detail))


# ---------------------------------------------------------------- session
class LoginIn(BaseModel):
    email: str
    password: str
    code: str | None = Field(None, max_length=10)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db), settings=Depends(get_settings_dep)):
    from marsad.security import decrypt, locked_out, record_attempt, verify_totp

    email, address = body.email.lower().strip(), client_address(request)
    if locked_out(db, email, address):
        raise HTTPException(429, "محاولات دخول فاشلة كثيرة. انتظر 15 دقيقة ثم حاول مجدداً.", headers={"Retry-After": "900"})
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        record_attempt(db, email, address, success=False)
        raise HTTPException(401, "البريد الإلكتروني أو كلمة المرور غير صحيحة")
    if user.totp_enabled:
        if not body.code:
            raise HTTPException(401, {"message": "أدخل رمز التحقق من تطبيق المصادقة", "otp_required": True})
        secret = decrypt(settings, user.totp_secret_enc or "")
        step = verify_totp(secret, body.code, user.totp_last_step) if secret else None
        if step is None:
            record_attempt(db, email, address, success=False)
            raise HTTPException(401, {"message": "رمز التحقق غير صحيح أو مستخدم من قبل", "otp_required": True})
        user.totp_last_step = step
    record_attempt(db, email, address, success=True)
    token = create_session(db, user)
    db.commit()
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role}}


@router.post("/logout")
def logout(token: str = Depends(bearer), db: Session = Depends(get_db)):
    end_session(db, token)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user), settings=Depends(get_settings_dep)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "totp_enabled": user.totp_enabled, "two_factor_required": settings.require_editor_2fa}


# ---------------------------------------------------------------- two-factor authentication
class CodeIn(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)


@router.post("/2fa/setup")
def two_factor_setup(user: User = Depends(current_user), db: Session = Depends(get_db), settings=Depends(get_settings_dep)):
    """Creates a new (not yet active) secret and returns it with a QR code for the authenticator app."""
    from marsad.security import encrypt, new_totp_secret, otpauth_uri, qr_svg

    if user.totp_enabled:
        raise HTTPException(409, "التحقق بخطوتين مفعّل. عطّله أولاً لإعادة الإعداد.")
    secret = new_totp_secret()
    user.totp_secret_enc, user.totp_last_step = encrypt(settings, secret), None
    db.commit()
    uri = otpauth_uri(secret, user.email, settings.site_name)
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": qr_svg(uri)}


@router.post("/2fa/enable")
def two_factor_enable(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db),
                      settings=Depends(get_settings_dep)):
    from marsad.security import decrypt, verify_totp

    secret = decrypt(settings, user.totp_secret_enc or "")
    step = verify_totp(secret, body.code, None) if secret else None
    if step is None:
        raise HTTPException(400, "الرمز غير صحيح. تأكد من ضبط ساعة الهاتف ثم أعد المحاولة.")
    user.totp_enabled, user.totp_last_step = True, step
    _audit(db, user, "2fa_enable", "user", user.id)
    db.commit()
    return {"totp_enabled": True}


@router.post("/2fa/disable")
def two_factor_disable(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db),
                       settings=Depends(get_settings_dep)):
    from marsad.security import decrypt, verify_totp

    secret = decrypt(settings, user.totp_secret_enc or "")
    step = verify_totp(secret, body.code, user.totp_last_step) if secret and user.totp_enabled else None
    if step is None:
        raise HTTPException(400, "الرمز غير صحيح")
    user.totp_enabled, user.totp_secret_enc, user.totp_last_step = False, None, None
    _audit(db, user, "2fa_disable", "user", user.id)
    db.commit()
    return {"totp_enabled": False}


# ---------------------------------------------------------------- queue and stats
QUEUE_STAGES = {
    "review": [Stage.review],
    "failed": [Stage.failed],
    "published": [Stage.published],
    "rejected": [Stage.rejected],
    "processing": [Stage.discovered, Stage.extracted, Stage.classified, Stage.summarized],
}


@router.get("/queue")
def queue(stage: str = Query("review"), page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200),
          user: User = Depends(current_user), db: Session = Depends(get_db)):
    stages = QUEUE_STAGES.get(stage)
    if stages is None:
        raise HTTPException(400, "مرحلة غير معروفة")
    q = select(Document).where(Document.stage.in_(stages)).options(*_LOAD)
    if stage == "review":
        q = q.order_by(Document.importance.desc().nulls_last(), Document.created_at)
    else:
        q = q.order_by(Document.updated_at.desc())
    total = db.scalar(select(func.count()).select_from(Document).where(Document.stage.in_(stages)))
    rows = db.scalars(q.offset((page - 1) * per_page).limit(per_page)).all()
    return {"items": [queue_row(d) for d in rows], "total": total, "page": page}


@router.get("/stats")
def stats(user: User = Depends(current_user), db: Session = Depends(get_db), settings=Depends(get_settings_dep)):
    by_stage = dict(db.execute(select(Document.stage, func.count()).group_by(Document.stage)).all())
    sources = db.scalars(select(Source).where(Source.is_active).order_by(Source.name)).all()
    open_feedback = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.resolved.is_(False)))
    proposed = db.scalar(select(func.count()).select_from(GlossaryTerm).where(GlossaryTerm.status == "proposed"))
    return {
        "stages": {s.value: by_stage.get(s, 0) for s in Stage},
        "spent_today_usd": round(spent_today(db), 4),
        "daily_budget_usd": settings.daily_budget_usd,
        "open_feedback": open_feedback,
        "proposed_terms": proposed,
        "sources": [{"slug": s.slug, "name": s.name, "name_ar": s.name_ar, "rights_level": s.rights_level.value,
                     "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                     "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
                     "last_error": s.last_error} for s in sources],
    }


# ---------------------------------------------------------------- items
@router.get("/items/{doc_id}")
def get_item(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return editor_item(_doc(db, doc_id))


class ItemPatch(BaseModel):
    title_ar: str | None = Field(None, max_length=500)
    summary: dict | None = None
    paragraphs: dict[int, str] | None = None
    publish_level: PublishLevel | None = None


SUMMARY_KEYS = {"dek_ar", "thesis_ar", "key_points_ar", "evidence_ar", "recommendations_ar", "significance_ar", "quotes"}


@router.patch("/items/{doc_id}")
def patch_item(doc_id: int, body: ItemPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(db, doc_id)
    tr = doc.translation
    if tr is None:
        raise HTTPException(409, "لا توجد ترجمة لهذه المادة بعد")
    changes: dict = {}
    if body.title_ar is not None and body.title_ar != tr.title_ar:
        changes["title_ar"] = [tr.title_ar, body.title_ar]
        tr.title_ar = body.title_ar
        tr.summary = {**tr.summary, "title_ar": body.title_ar}
    if body.summary:
        unknown = set(body.summary) - SUMMARY_KEYS
        if unknown:
            raise HTTPException(400, f"حقول غير معروفة: {', '.join(sorted(unknown))}")
        changes["summary"] = {k: [tr.summary.get(k), v] for k, v in body.summary.items() if tr.summary.get(k) != v}
        tr.summary = {**tr.summary, **body.summary}
    if body.paragraphs:
        if not tr.paragraphs_ar:
            raise HTTPException(409, "هذه المادة ملخص فقط ولا تحتوي نصاً مترجماً")
        paras = list(tr.paragraphs_ar)
        for idx, text in body.paragraphs.items():
            if not 0 <= idx < len(paras):
                raise HTTPException(400, f"رقم فقرة غير صحيح: {idx}")
            if paras[idx] != text:
                changes.setdefault("paragraphs", {})[idx] = [paras[idx], text]
                paras[idx] = text
        tr.paragraphs_ar = paras
    if body.publish_level is not None:
        if body.publish_level == PublishLevel.full and doc.max_level != PublishLevel.full:
            raise HTTPException(403, "حقوق المصدر لا تسمح بنشر النص الكامل")
        changes["publish_level"] = [tr.publish_level.value, body.publish_level.value]
        tr.publish_level = body.publish_level
    if changes:
        _audit(db, user, "edit", "document", doc.id, **changes)
        if doc.stage == Stage.published:
            tr.search_text = build_search_text(doc, tr)
    db.commit()
    return editor_item(doc)


@router.post("/items/{doc_id}/publish")
def publish_item(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(db, doc_id)
    if doc.stage not in (Stage.review, Stage.published) or doc.translation is None:
        raise HTTPException(409, "لا يمكن نشر مادة في هذه المرحلة")
    publish(db, doc, user)
    db.commit()
    return editor_item(doc)


class RejectIn(BaseModel):
    reason: str = Field("", max_length=1000)


@router.post("/items/{doc_id}/reject")
def reject_item(doc_id: int, body: RejectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(db, doc_id)
    doc.stage, doc.error = Stage.rejected, body.reason or None
    _audit(db, user, "reject", "document", doc.id, reason=body.reason)
    db.commit()
    return editor_item(doc)


@router.post("/items/{doc_id}/unpublish")
def unpublish_item(doc_id: int, body: RejectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Takedown: removes the item from the public site immediately (e.g. on a rights complaint)."""
    doc = _doc(db, doc_id)
    if doc.stage != Stage.published:
        raise HTTPException(409, "المادة غير منشورة")
    doc.stage = Stage.review
    _audit(db, user, "unpublish", "document", doc.id, reason=body.reason)
    db.commit()
    return editor_item(doc)


@router.post("/items/{doc_id}/retry")
def retry_item(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _doc(db, doc_id)
    if doc.stage not in (Stage.failed, Stage.rejected):
        raise HTTPException(409, "إعادة المحاولة متاحة للمواد المتعثرة أو المرفوضة فقط")
    doc.stage, doc.attempts, doc.error = Stage.discovered, 0, None
    _audit(db, user, "retry", "document", doc.id)
    db.commit()
    return editor_item(doc)


class LicenseIn(BaseModel):
    license: str = Field(..., min_length=2, max_length=64)
    evidence: str = Field(..., min_length=5, max_length=2000)


@router.post("/items/{doc_id}/license")
def set_item_license(doc_id: int, body: LicenseIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Record an item-level open licence (e.g. an open-access article) and reprocess the item with its full text."""
    doc = _doc(db, doc_id)
    before = [doc.item_license, doc.item_rights_evidence]
    doc.item_license, doc.item_rights_evidence = body.license.strip(), body.evidence.strip()
    if doc.stage == Stage.published:
        raise HTTPException(409, "أزل المادة من الموقع أولاً ثم سجّل الترخيص لإعادة معالجتها")
    doc.stage, doc.attempts, doc.error = Stage.discovered, 0, None
    _audit(db, user, "item_license", "document", doc.id, before=before, after=[doc.item_license, doc.item_rights_evidence])
    db.commit()
    return editor_item(doc)


@router.post("/items/{doc_id}/paragraphs/{idx}/retranslate")
def retranslate_paragraph(doc_id: int, idx: int, user: User = Depends(current_user), db: Session = Depends(get_db),
                          llm=Depends(get_llm), settings=Depends(get_settings_dep)):
    """Returns a fresh translation suggestion for one paragraph; nothing is saved."""
    doc = _doc(db, doc_id)
    if doc.max_level != PublishLevel.full or not 0 <= idx < len(doc.paragraphs_en or []):
        raise HTTPException(400, "لا يمكن ترجمة هذه الفقرة")
    context = (doc.translation.summary or {}).get("thesis_ar", "") if doc.translation else ""
    text, notes, res = translate_one(llm, doc_input(doc), idx, load_terms(db, doc.language or "en"), settings,
                                     context_ar=context)
    record_usage(db, doc, "retranslate", res)
    db.commit()
    return {"index": idx, "ar": text, "notes": notes}


# ---------------------------------------------------------------- manual import
class ImportIn(BaseModel):
    url: str = Field(..., max_length=1000)
    source_slug: str
    title: str = Field("", max_length=500)


def _safe_url(url: str) -> str:
    """Editors can import any public page or PDF, but never internal addresses (the worker fetches it)."""
    import ipaddress
    from urllib.parse import urlsplit

    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(400, "الرابط يجب أن يبدأ بـ https://")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise HTTPException(400, "لا يمكن استيراد عنوان داخلي")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url.strip()
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise HTTPException(400, "لا يمكن استيراد عنوان داخلي")
    return url.strip()


@router.post("/import", status_code=201)
def import_item(body: ImportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Queue a single page or PDF (e.g. a Studies in Intelligence article) for the normal pipeline."""
    from marsad.models import RawItem
    from marsad.normalize import url_hash

    url = _safe_url(body.url)
    src = db.scalar(select(Source).where(Source.slug == body.source_slug))
    if src is None:
        raise HTTPException(404, "المصدر غير موجود")
    h = url_hash(url)
    existing = db.scalar(select(Document).join(RawItem).where(RawItem.url_hash == h))
    if existing is not None:
        raise HTTPException(409, f"هذا الرابط مستورد من قبل (المادة {existing.id})")
    raw = RawItem(source_id=src.id, url=url, url_hash=h, title=body.title.strip())
    db.add(raw)
    db.flush()
    doc = Document(source_id=src.id, raw_item_id=raw.id, url=url, title_en=body.title.strip(), stage=Stage.discovered)
    db.add(doc)
    db.flush()
    _audit(db, user, "import", "document", doc.id, url=url, source=src.slug)
    db.commit()
    return {"id": doc.id, "stage": doc.stage.value}


# ---------------------------------------------------------------- glossary
class TermIn(BaseModel):
    lang: str = Field("en", pattern="^[a-z]{2}$")
    term_en: str = Field(..., min_length=1, max_length=200)
    term_ar: str = Field(..., min_length=1, max_length=200)
    variants_ar: list[str] = []
    definition_ar: str = ""
    domain: str = "general"
    status: str = Field("approved", pattern="^(approved|proposed)$")


def _term_json(t: GlossaryTerm) -> dict:
    return {"id": t.id, "lang": t.lang, "term_en": t.term_en, "term_ar": t.term_ar, "variants_ar": t.variants_ar,
            "definition_ar": t.definition_ar, "domain": t.domain, "status": t.status,
            "proposal_count": t.proposal_count, "example_document_id": t.example_document_id}


@router.get("/glossary")
def list_terms(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(GlossaryTerm).order_by(GlossaryTerm.status.desc(), GlossaryTerm.proposal_count.desc(),
                                      GlossaryTerm.term_en)
    if status:
        q = q.where(GlossaryTerm.status == status)
    return [_term_json(t) for t in db.scalars(q).all()]


@router.post("/glossary")
def upsert_term(body: TermIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    term = db.scalar(select(GlossaryTerm).where(GlossaryTerm.lang == body.lang,
                                                func.lower(GlossaryTerm.term_en) == body.term_en.lower().strip()))
    before = _term_json(term) if term else None
    if term is None:
        term = GlossaryTerm(lang=body.lang, term_en=body.term_en.strip(), created_by=user.id)
        db.add(term)
    term.term_ar, term.variants_ar = body.term_ar.strip(), [v.strip() for v in body.variants_ar if v.strip()]
    term.definition_ar, term.domain, term.status = body.definition_ar, body.domain, body.status
    db.flush()
    _audit(db, user, "glossary_upsert", "glossary", term.id, before=before, after=_term_json(term))
    db.commit()
    return _term_json(term)


@router.delete("/glossary/{term_id}")
def delete_term(term_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    term = db.get(GlossaryTerm, term_id)
    if term is None:
        raise HTTPException(404, "المصطلح غير موجود")
    _audit(db, user, "glossary_delete", "glossary", term.id, before=_term_json(term))
    db.delete(term)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- feedback
@router.get("/feedback")
def list_feedback(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).where(Feedback.resolved.is_(False)).order_by(Feedback.created_at.desc())).all()
    return [{"id": f.id, "document_id": f.document_id, "paragraph_index": f.paragraph_index, "message": f.message,
             "created_at": f.created_at.isoformat()} for f in rows]


@router.post("/feedback/{fid}/resolve")
def resolve_feedback(fid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    f = db.get(Feedback, fid)
    if f is None:
        raise HTTPException(404, "غير موجود")
    f.resolved = True
    _audit(db, user, "feedback_resolve", "feedback", f.id)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- sources (admin)
class SourcePatch(BaseModel):
    rights_level: RightsLevel | None = None
    license: str | None = None
    rights_evidence: str | None = None
    is_active: bool | None = None
    feed_url: str | None = None


@router.patch("/sources/{slug}")
def patch_source(slug: str, body: SourcePatch, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    src = db.scalar(select(Source).where(Source.slug == slug))
    if src is None:
        raise HTTPException(404, "المصدر غير موجود")
    changes = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        old = getattr(src, field)
        old = old.value if hasattr(old, "value") else old
        new = value.value if hasattr(value, "value") else value
        if old != new:
            changes[field] = [old, new]
            setattr(src, field, value)
    if changes.get("rights_level") and not (body.rights_evidence or src.rights_evidence):
        raise HTTPException(400, "يجب توثيق دليل الحقوق (رابط الترخيص أو الإذن) عند تغيير مستوى الحقوق")
    _audit(db, user, "source_update", "source", src.id, **changes)
    db.commit()
    return {"slug": src.slug, "rights_level": src.rights_level.value, "license": src.license,
            "is_active": src.is_active, "feed_url": src.feed_url, "rights_evidence": src.rights_evidence}


# ---------------------------------------------------------------- API clients (admin)
class ApiClientIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    organization: str = Field("", max_length=200)
    contact_email: str = Field("", max_length=320)
    rate_limit_per_minute: int = Field(60, ge=1, le=6000)


def _client_json(db: Session, c) -> dict:
    from datetime import datetime, timedelta, timezone

    from marsad.models import ApiUsage

    since = datetime.now(timezone.utc) - timedelta(days=30)
    total = db.scalar(select(func.coalesce(func.sum(ApiUsage.count), 0)).where(
        ApiUsage.client_id == c.id, ApiUsage.window_start >= since))
    return {"id": c.id, "name": c.name, "organization": c.organization, "contact_email": c.contact_email,
            "key_prefix": c.key_prefix, "rate_limit_per_minute": c.rate_limit_per_minute, "is_active": c.is_active,
            "created_at": c.created_at.isoformat(), "requests_30d": int(total),
            "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None}


@router.get("/api-clients")
def list_api_clients(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    from marsad.models import ApiClient

    return [_client_json(db, c) for c in db.scalars(select(ApiClient).order_by(ApiClient.created_at.desc())).all()]


@router.post("/api-clients", status_code=201)
def create_api_client(body: ApiClientIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    """The key is returned once, here; only its hash is stored."""
    from marsad.api.keys import new_key
    from marsad.models import ApiClient

    key, key_hash, prefix = new_key()
    c = ApiClient(name=body.name, organization=body.organization, contact_email=body.contact_email,
                  rate_limit_per_minute=body.rate_limit_per_minute, key_hash=key_hash, key_prefix=prefix)
    db.add(c)
    db.flush()
    _audit(db, user, "api_client_create", "api_client", c.id, name=c.name)
    db.commit()
    return {**_client_json(db, c), "key": key}


class ApiClientPatch(BaseModel):
    rate_limit_per_minute: int | None = Field(None, ge=1, le=6000)
    is_active: bool | None = None


@router.patch("/api-clients/{client_id}")
def patch_api_client(client_id: int, body: ApiClientPatch, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    from marsad.models import ApiClient

    c = db.get(ApiClient, client_id)
    if c is None:
        raise HTTPException(404, "غير موجود")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(c, k, v)
    _audit(db, user, "api_client_update", "api_client", c.id, **changes)
    db.commit()
    return _client_json(db, c)
