"""Monthly trend statistics across monitored sources, and editor-reviewed monthly reports."""

import json
import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from marsad.ai import prompts, schemas
from marsad.ai.llm import LLM
from marsad.config import Settings
from marsad.models import AiUsage, Document, DocumentTag, Stage, TrendReport, utcnow

MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
COUNTED = (Stage.classified, Stage.summarized, Stage.translated, Stage.review, Stage.published)
SMALL_SAMPLE = 10


def month_bounds(month: str) -> tuple[datetime, datetime]:
    m = MONTH.match(month)
    if not m:
        raise ValueError("month must be YYYY-MM")
    y, mo = int(m.group(1)), int(m.group(2))
    start = datetime(y, mo, 1, tzinfo=timezone.utc)
    end = datetime(y + (mo == 12), 1 if mo == 12 else mo + 1, 1, tzinfo=timezone.utc)
    return start, end


def shift(month: str, delta: int) -> str:
    y, mo = map(int, month.split("-"))
    idx = y * 12 + (mo - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _docs(session: Session, month: str) -> list[Document]:
    start, end = month_bounds(month)
    return list(session.scalars(
        select(Document).where(Document.stage.in_(COUNTED), Document.published_at >= start, Document.published_at < end)
        .options(selectinload(Document.tags).selectinload(DocumentTag.term), selectinload(Document.source),
                 selectinload(Document.translation))).all())


def _counts(docs: list[Document]) -> dict[str, Counter]:
    out = {"topic": Counter(), "region": Counter(), "doc_type": Counter(), "source": Counter(), "keyword": Counter()}
    for d in docs:
        for t in d.tags:
            out[t.term.kind][t.term.slug] += 1
        out["source"][d.source.slug] += 1
        for k in {k.strip().lower() for k in d.keywords or [] if k.strip()}:
            out["keyword"][k] += 1
    return out


def compute(session: Session, month: str) -> dict:
    docs = _docs(session, month)
    now_c = _counts(docs)
    prev_c = _counts(_docs(session, shift(month, -1)))
    base = [_counts(_docs(session, shift(month, -i))) for i in (1, 2, 3)]

    names: dict[tuple[str, str], str] = {}
    for d in docs:
        for t in d.tags:
            names[(t.term.kind, t.term.slug)] = t.term.name_ar
        names[("source", d.source.slug)] = d.source.name_ar

    def rows(kind: str) -> list[dict]:
        out = []
        for slug in set(now_c[kind]) | set(prev_c[kind]):
            cur, prev = now_c[kind][slug], prev_c[kind][slug]
            avg3 = sum(b[kind][slug] for b in base) / 3
            out.append({"slug": slug, "name_ar": names.get((kind, slug), slug), "count": cur, "previous": prev,
                        "change": cur - prev, "avg_3m": round(avg3, 1)})
        return sorted(out, key=lambda r: (-r["count"], r["slug"]))

    topics = rows("topic")
    movers = [r for r in topics if max(r["count"], r["previous"]) >= 2]
    rising = sorted((r for r in movers if r["count"] - r["avg_3m"] > 0), key=lambda r: -(r["count"] - r["avg_3m"]))[:5]
    falling = sorted((r for r in movers if r["count"] - r["avg_3m"] < 0), key=lambda r: r["count"] - r["avg_3m"])[:5]
    keywords = [{"keyword": k, "count": c, "previous": prev_c["keyword"][k]}
                for k, c in now_c["keyword"].most_common(40) if c >= 2]
    rising_keywords = sorted((k for k in keywords if k["count"] > k["previous"]),
                             key=lambda k: -(k["count"] - k["previous"]))[:10]

    start, _ = month_bounds(month)
    weeks = Counter(min(4, (d.published_at.day - 1) // 7) for d in docs)
    top = sorted((d for d in docs if d.stage == Stage.published and (d.importance or 0) >= 4),
                 key=lambda d: (-(d.importance or 0), d.published_at), )[:8]
    total, prev_total = len(docs), sum(prev_c["source"].values())
    return {
        "month": month, "total": total, "previous_total": prev_total, "empty": total == 0,
        "small_sample": 0 < total < SMALL_SAMPLE,
        "topics": topics, "regions": rows("region"), "sources": rows("source"), "doc_types": rows("doc_type"),
        "rising_topics": rising, "falling_topics": falling, "rising_keywords": rising_keywords,
        "weeks": [{"week": w + 1, "count": weeks.get(w, 0)} for w in range(5)],
        "top_items": [{"id": d.id, "title_ar": d.translation.title_ar if d.translation else d.title_en,
                       "source": d.source.name_ar, "importance": d.importance} for d in top],
    }


def available_months(session: Session) -> list[str]:
    dates = session.scalars(select(Document.published_at).where(Document.stage.in_(COUNTED),
                                                                Document.published_at.is_not(None))).all()
    return sorted({f"{d.year:04d}-{d.month:02d}" for d in dates}, reverse=True)


def draft_report(session: Session, month: str, llm: LLM, settings: Settings) -> TrendReport:
    stats = compute(session, month)
    if stats["empty"]:
        raise ValueError("no items for this month")
    report = session.scalar(select(TrendReport).where(TrendReport.month == month)) or TrendReport(month=month)
    session.add(report)
    payload = {k: stats[k] for k in ("month", "total", "previous_total", "small_sample", "rising_topics",
                                     "falling_topics", "rising_keywords", "top_items")}
    payload["topics"] = stats["topics"][:10]
    payload["sources"] = stats["sources"][:8]
    res = llm.json(task="trend_narrative", model=settings.model_summarize, system=prompts.TREND_NARRATIVE,
                   user=json.dumps(payload, ensure_ascii=False), schema=schemas.TREND_NARRATIVE, max_tokens=4000,
                   effort=settings.effort_translate)
    session.add(AiUsage(task="trend_narrative", model=res.model, input_tokens=res.input_tokens,
                        output_tokens=res.output_tokens, cost_usd=res.cost_usd))
    report.stats, report.narrative_ar, report.narrative_is_draft = stats, res.data["narrative_ar"].strip(), True
    report.status = "draft" if report.status != "published" else report.status
    return report


def ensure_previous_month_draft(session: Session, llm: LLM, settings: Settings, at: datetime | None = None) -> bool:
    """Worker hook: once a month is over, prepare its report draft for the editor (once)."""
    at = at or utcnow()
    month = shift(f"{at.year:04d}-{at.month:02d}", -1)
    if session.scalar(select(TrendReport.id).where(TrendReport.month == month)):
        return False
    try:
        draft_report(session, month, llm, settings)
    except ValueError:
        return False
    session.commit()
    return True
