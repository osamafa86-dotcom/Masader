"""Worker: fetch due sources, then move documents through the pipeline."""

import logging
import time

from sqlalchemy.orm import Session, sessionmaker

from marsad.ai.llm import LLM, AnthropicLLM, FakeLLM, GeminiLLM
from marsad.config import Settings
from marsad.embed import embed_pending, make_embedder
from marsad.newsletter.mailer import make_mailer
from marsad.newsletter.service import deliver_pending, ensure_weekly_draft
from marsad.monitoring import heartbeat, init_sentry, send_alerts
from marsad.trends import ensure_previous_month_draft
from marsad.fetch.http import PoliteClient
from marsad.fetch.run import due_sources, fetch_source
from marsad.models import Stage
from marsad.batches import collect, submit_pending, supports_batches
from marsad.pipeline import AI_STAGES, advance, claim_next, not_batched, spent_today
from marsad.storage import LocalStorage

log = logging.getLogger(__name__)


def make_llm(settings: Settings) -> LLM:
    if settings.llm_backend == "fake":
        from marsad.ai.demo import demo_handler

        return FakeLLM(demo_handler)
    if settings.llm_backend == "gemini":
        return GeminiLLM(api_key=settings.gemini_api_key or None, model=settings.gemini_model,
                         model_light=settings.gemini_model_light)
    return AnthropicLLM()


def _drain(factory: sessionmaker[Session], stages: tuple[Stage, ...], limit: int, settings: Settings,
           budget_check: bool, extra=None, **deps) -> int:
    done = 0
    seen: set[int] = set()
    while done < limit:
        with factory() as session:
            if budget_check and spent_today(session) >= settings.daily_budget_usd:
                log.warning("daily AI budget of $%.2f reached; AI stages paused", settings.daily_budget_usd)
                return done
            doc = claim_next(session, stages, exclude=seen, extra=extra)  # one step per document per round
            if doc is None:
                session.rollback()
                return done
            seen.add(doc.id)
            before = doc.stage
            after = advance(session, doc, settings=settings, **deps)  # glossary loaded per document language
            session.commit()
            log.info("document %s: %s -> %s", doc.id, before.value, after.value)
            done += 1
    return done


def run_once(factory: sessionmaker[Session], llm: LLM, client: PoliteClient, settings: Settings,
             embedder=None, mailer=None) -> dict:
    storage = LocalStorage(settings.storage_dir)
    counts = {"fetched": 0, "extracted": 0, "ai_steps": 0}
    with factory() as session:
        for source in due_sources(session):
            counts["fetched"] += fetch_source(session, source, client)
    deps = dict(llm=llm, client=client, storage=storage)
    counts["extracted"] = _drain(factory, (Stage.discovered,), settings.worker_batch * 4, settings, False, **deps)
    # Later stages first, so documents already in flight finish before new ones start.
    use_batches = settings.batch_enabled and supports_batches(llm)
    if use_batches:
        with factory() as session:
            counts["batch_collected"] = collect(session, llm, settings)
    for stage in reversed(AI_STAGES):
        extra = not_batched(settings if use_batches else settings.model_copy(update={"batch_enabled": False})) \
            if stage == Stage.summarized else None
        counts["ai_steps"] += _drain(factory, (stage,), settings.worker_batch, settings, True, extra=extra, **deps)
    if use_batches:
        with factory() as session:
            if spent_today(session) < settings.daily_budget_usd:
                counts["batch_submitted"] = submit_pending(session, llm, settings)
    if embedder is not None:
        with factory() as session:
            counts["embedded"] = embed_pending(session, embedder)
    with factory() as session:
        if ensure_previous_month_draft(session, llm, settings):
            counts["trend_draft"] = 1
    with factory() as session:
        if ensure_weekly_draft(session, settings):
            counts["digest_draft"] = 1
        if mailer is not None:
            counts["emails"] = deliver_pending(session, mailer, settings, settings.mail_batch)
    with factory() as session:
        heartbeat(session, counts)
        counts["alerts"] = send_alerts(session, mailer, settings)
    return counts


def run_forever(factory: sessionmaker[Session], settings: Settings) -> None:
    llm, client, embedder = make_llm(settings), PoliteClient(settings), make_embedder(settings)
    mailer = make_mailer(settings)
    init_sentry(settings, "worker")
    log.info("worker started (llm=%s, interval=%ss)", settings.llm_backend, settings.worker_interval_s)
    while True:
        try:
            counts = run_once(factory, llm, client, settings, embedder, mailer)
            log.info("cycle done: %s", counts)
        except Exception:  # noqa: BLE001
            log.exception("worker cycle failed")
        time.sleep(settings.worker_interval_s)
