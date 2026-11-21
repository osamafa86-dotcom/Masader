"""Half-price translation of non-urgent items through the Message Batches API (strategy plan 5.2).

Cycle N: submit_pending() sends the translation chunks of eligible items as one batch.
Cycle N+k: collect() fetches results once the batch has ended; anything missing, errored or expired is retried
synchronously, then the item goes through the same QA and routing as any other translation."""

import logging
import secrets
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marsad.ai.llm import LLM, BatchItem, LLMError, LLMResult
from marsad.ai.tasks import TranslationIncomplete, chunk_ids, complete_translation, parse_translation, translation_request
from marsad.config import Settings
from marsad.models import AiBatch, AiBatchRequest, Document, PublishLevel, Stage, utcnow
from marsad.pipeline import MAX_ATTEMPTS, apply_translation, doc_input, load_terms, record_usage

log = logging.getLogger(__name__)
STALE_AFTER = timedelta(hours=26)  # batches end within 24 hours; after that, translate synchronously


def supports_batches(llm: LLM) -> bool:
    return hasattr(llm, "batch_submit")


def _eligible(session: Session, settings: Settings, limit: int) -> list[Document]:
    return list(session.scalars(
        select(Document).where(Document.stage == Stage.summarized, Document.in_batch_id.is_(None),
                               Document.max_level == PublishLevel.full, Document.language != "ar",
                               Document.importance <= settings.batch_max_importance,
                               func.jsonb_array_length(Document.paragraphs_en) > 0)
        .order_by(Document.created_at).limit(limit).with_for_update(skip_locked=True)).all())


def submit_pending(session: Session, llm: LLM, settings: Settings) -> int:
    docs = _eligible(session, settings, settings.batch_max_docs)
    if not docs:
        return 0
    items: list[BatchItem] = []
    plan: list[tuple[Document, str, list[int]]] = []
    for doc in docs:
        terms = load_terms(session, doc.language or "en")
        di = doc_input(doc)
        context = (doc.translation.summary or {}).get("thesis_ar", "")
        for k, ids in enumerate(chunk_ids(di.paragraphs, settings.chunk_words)):
            custom_id = f"d{doc.id}-c{k}-{secrets.token_hex(4)}"
            items.append(BatchItem(custom_id=custom_id, **translation_request(di, ids, terms, context, settings)))
            plan.append((doc, custom_id, ids))
    try:
        provider_id = llm.batch_submit(items)
    except LLMError as exc:
        log.warning("batch submission failed, will retry next cycle: %s", exc)
        session.rollback()
        return 0
    batch = AiBatch(provider_id=provider_id, request_count=len(items))
    session.add(batch)
    session.flush()
    for doc, custom_id, ids in plan:
        session.add(AiBatchRequest(custom_id=custom_id, batch_id=batch.id, document_id=doc.id, paragraph_ids=ids))
        doc.in_batch_id = batch.id
    session.commit()
    log.info("submitted batch %s: %d requests for %d items", provider_id, len(items), len(docs))
    return len(docs)


def collect(session: Session, llm: LLM, settings: Settings) -> int:
    finished = 0
    for batch in session.scalars(select(AiBatch).where(AiBatch.status == "submitted")).all():
        stale = utcnow() - batch.created_at > STALE_AFTER
        try:
            ended = llm.batch_status(batch.provider_id) == "ended"
        except Exception as exc:  # noqa: BLE001 - provider hiccup: try again next cycle
            log.warning("batch %s status unavailable: %s", batch.provider_id, exc)
            ended = False
        if not ended and not stale:
            continue
        try:
            results = llm.batch_results(batch.provider_id) if ended else {}
        except Exception as exc:  # noqa: BLE001
            log.warning("batch %s results unavailable: %s", batch.provider_id, exc)
            if not stale:
                continue
            results = {}
        by_doc: dict[int, list[AiBatchRequest]] = defaultdict(list)
        for req in session.scalars(select(AiBatchRequest).where(AiBatchRequest.batch_id == batch.id)).all():
            by_doc[req.document_id].append(req)
        for doc_id, reqs in by_doc.items():
            doc = session.get(Document, doc_id)
            if doc is None or doc.in_batch_id != batch.id:
                continue
            doc.in_batch_id = None
            if doc.stage != Stage.summarized:
                continue
            got: dict[int, str] = {}
            notes: list[dict] = []
            for req in reqs:
                r = results.get(req.custom_id)
                if isinstance(r, LLMResult):
                    record_usage(session, doc, "translate_batch", r)
                    doc.translation.cost_usd += r.cost_usd
                    g, n = parse_translation(r.data, req.paragraph_ids)
                    got.update(g)
                    notes += n
                elif r is not None:
                    log.info("batch request %s: %s; retrying synchronously", req.custom_id, r)
            terms = load_terms(session, doc.language or "en")
            context = (doc.translation.summary or {}).get("thesis_ar", "")
            try:
                result = complete_translation(llm, doc_input(doc), got, notes, terms, settings, context)
                apply_translation(session, doc, result, terms, settings, llm)
                doc.error = None
            except (TranslationIncomplete, LLMError) as exc:
                doc.attempts += 1
                doc.error = f"{type(exc).__name__}: {exc}"[:2000]
                if doc.attempts >= MAX_ATTEMPTS:
                    doc.stage = Stage.failed
            finished += 1
        batch.status, batch.collected_at = "collected", utcnow()
        session.commit()
    return finished
