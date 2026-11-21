"""Weekly quality sample of items published without human review (strategy plan 5.5)."""

import hashlib
import math
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.models import Document, Stage, Translation, utcnow

SAMPLE_RATE = 0.10
WINDOW = timedelta(days=7)


def _rank(doc_id: int, week: str) -> str:
    return hashlib.sha256(f"{week}:{doc_id}".encode()).hexdigest()


def current_sample(session: Session) -> list[Document]:
    """A stable random 10% (at least one) of last week's machine-only publications, minus those already checked."""
    since = utcnow() - WINDOW
    week = utcnow().strftime("%G-W%V")
    pool = list(session.scalars(
        select(Document).join(Translation).where(Document.stage == Stage.published,
                                                 Translation.human_reviewed.is_(False),
                                                 Translation.published_at >= since)).all())
    if not pool:
        return []
    size = max(1, math.ceil(len(pool) * SAMPLE_RATE))
    chosen = sorted(pool, key=lambda d: _rank(d.id, week))[:size]
    return [d for d in chosen if d.translation.sampled_at is None]
