"""Trend endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.api.auth import current_user
from marsad.api.deps import get_db, get_llm, get_settings_dep
from marsad import trends
from marsad.models import AuditLog, TrendReport, User, utcnow

public = APIRouter(prefix="/api")
editor = APIRouter(prefix="/api/editor")


def _month(month: str) -> str:
    try:
        trends.month_bounds(month)
    except ValueError:
        raise HTTPException(422, "صيغة الشهر YYYY-MM")
    return month


def _report_json(r: TrendReport | None, include_draft: bool) -> dict | None:
    if r is None or (r.status != "published" and not include_draft):
        return None
    return {"month": r.month, "status": r.status, "narrative_ar": r.narrative_ar, "narrative_is_draft": r.narrative_is_draft,
            "published_at": r.published_at.isoformat() if r.published_at else None}


@public.get("/trends/months")
def months(db: Session = Depends(get_db)):
    published = set(db.scalars(select(TrendReport.month).where(TrendReport.status == "published")).all())
    return [{"month": m, "report": m in published} for m in trends.available_months(db)]


@public.get("/trends/{month}")
def month_stats(month: str, db: Session = Depends(get_db)):
    month = _month(month)
    report = db.scalar(select(TrendReport).where(TrendReport.month == month))
    return {**trends.compute(db, month), "report": _report_json(report, include_draft=False)}


@editor.get("/trends/{month}")
def editor_month(month: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    month = _month(month)
    report = db.scalar(select(TrendReport).where(TrendReport.month == month))
    return {**trends.compute(db, month), "report": _report_json(report, include_draft=True)}


@editor.post("/trends/{month}/draft")
def draft(month: str, user: User = Depends(current_user), db: Session = Depends(get_db), llm=Depends(get_llm),
          settings=Depends(get_settings_dep)):
    month = _month(month)
    try:
        report = trends.draft_report(db, month, llm, settings)
    except ValueError:
        raise HTTPException(409, "لا توجد مواد مرصودة في هذا الشهر")
    db.commit()
    return _report_json(report, include_draft=True)


class NarrativeIn(BaseModel):
    narrative_ar: str = Field(..., min_length=20, max_length=8000)


@editor.patch("/trends/{month}")
def save(month: str, body: NarrativeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = db.scalar(select(TrendReport).where(TrendReport.month == _month(month)))
    if report is None:
        raise HTTPException(404, "أعدّ مسودة التقرير أولاً")
    report.narrative_ar, report.narrative_is_draft = body.narrative_ar.strip(), False
    db.commit()
    return _report_json(report, include_draft=True)


@editor.post("/trends/{month}/publish")
def publish(month: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = db.scalar(select(TrendReport).where(TrendReport.month == _month(month)))
    if report is None:
        raise HTTPException(404, "أعدّ مسودة التقرير أولاً")
    if report.narrative_is_draft:
        raise HTTPException(409, "القراءة مقترحة من النموذج: راجعها واحفظها قبل النشر")
    report.status, report.published_at = "published", report.published_at or utcnow()
    db.add(AuditLog(user_id=user.id, action="trend_publish", entity="trend_report", entity_id=report.id, detail={"month": report.month}))
    db.commit()
    return _report_json(report, include_draft=True)
