"""Document stage machine: discovered → extracted → classified → summarized → review/published."""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from marsad.ai.glossary import Term
from marsad.ai.llm import LLM, LLMRefusal, LLMResult
from marsad.ai.prompts import PROMPT_VERSION
from marsad.ai.tasks import DocInput, classify, qa_check, summarize, translate, translate_one
from marsad.arabic import loose_form, normalize_ar
from marsad.config import Settings
from marsad.extract.html import extract_html, find_pdf_link, paragraphs_from_fragment
from marsad.extract.pdf import extract_pdf
from marsad.extract.types import Extracted
from marsad.fetch.http import FetchError, PoliteClient
from marsad.authors import link_authors
from marsad.journals import clean_abstract, has_abstract
from marsad.models import (
    AiUsage,
    AuditLog,
    Document,
    DocumentTag,
    GlossaryTerm,
    PublishLevel,
    RawItem,
    Stage,
    TaxonomyTerm,
    Translation,
    User,
    utcnow,
)
from marsad.normalize import content_hash, url_hash, word_count
from marsad.rights import max_publish_level
from marsad.storage import LocalStorage

log = logging.getLogger(__name__)

MIN_BODY_WORDS = 80
FEED_FULLTEXT_WORDS = 250
MAX_ATTEMPTS = 3
AI_STAGES = (Stage.extracted, Stage.classified, Stage.summarized)


class Insufficient(Exception):
    pass


# ---------------------------------------------------------------- helpers
def load_terms(session: Session) -> list[Term]:
    rows = session.scalars(select(GlossaryTerm).where(GlossaryTerm.status == "approved")).all()
    return [Term(r.term_en, r.term_ar, tuple(r.variants_ar or ())) for r in rows]


def record_usage(session: Session, doc: Document, task: str, res: LLMResult) -> None:
    session.add(AiUsage(document_id=doc.id, task=task, model=res.model, input_tokens=res.input_tokens,
                        output_tokens=res.output_tokens, cost_usd=res.cost_usd))


def spent_today(session: Session) -> float:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return float(session.scalar(select(func.coalesce(func.sum(AiUsage.cost_usd), 0)).where(AiUsage.created_at >= start)))


def doc_input(doc: Document) -> DocInput:
    return DocInput(title=doc.title_en, paragraphs=list(doc.paragraphs_en or []), source_name=doc.source.name,
                    authors=list(doc.authors or []), abstract=doc.abstract_en)


def audit(session: Session, action: str, doc: Document, user: User | None = None, **detail) -> None:
    session.add(AuditLog(user_id=user.id if user else None, action=action, entity="document", entity_id=doc.id,
                         detail=detail))


# ---------------------------------------------------------------- steps
LANDING_PAGE_WORDS = 400  # an HTML page shorter than this with a PDF link is a report landing page
MAX_PDF_BYTES = 60 * 1024 * 1024


def _is_pdf(res) -> bool:
    return res.content_type == "application/pdf" or res.content[:5] == b"%PDF-"


def _store(storage: LocalStorage, doc: Document, raw: RawItem, url: str, content: bytes, pdf: bool) -> None:
    key = f"raw/{doc.source.slug}/{url_hash(url)[:16]}.{'pdf' if pdf else 'html'}"
    raw.raw_key = storage.put(key, content)
    raw.content_type = "application/pdf" if pdf else "text/html"


def _download_and_extract(doc: Document, raw: RawItem, client: PoliteClient, storage: LocalStorage) -> Extracted:
    res = client.get(doc.url)
    if _is_pdf(res):
        _store(storage, doc, raw, doc.url, res.content, True)
        return extract_pdf(res.content)
    html = res.content.decode("utf-8", "replace")
    _store(storage, doc, raw, doc.url, res.content, False)
    ex = extract_html(html, res.url)
    if word_count(ex.paragraphs) < LANDING_PAGE_WORDS:
        pdf_url = find_pdf_link(html, res.url)
        if pdf_url:
            try:
                pdf = client.get(pdf_url)
            except FetchError as exc:
                log.warning("document %s: report PDF not available (%s); using the landing page", doc.id, exc)
                return ex
            if _is_pdf(pdf) and len(pdf.content) <= MAX_PDF_BYTES:
                _store(storage, doc, raw, pdf_url, pdf.content, True)
                full = extract_pdf(pdf.content)
                if word_count(full.paragraphs) > word_count(ex.paragraphs):
                    # Keep the landing page's title, authors and summary; take the body from the PDF.
                    return Extracted(title=ex.title or full.title, paragraphs=full.paragraphs,
                                     authors=ex.authors or full.authors, published_at=ex.published_at,
                                     abstract=ex.abstract or (" ".join(ex.paragraphs) or None))
    return ex


def _extract_feed_only(doc: Document, raw: RawItem) -> None:
    """Journals: the article page is paywalled and never downloaded; work from the feed abstract (or title)."""
    mode = doc.source.content_mode
    abstract = clean_abstract(raw.feed_summary or raw.feed_content)
    if mode == "abstract" and not has_abstract(abstract):
        raise Insufficient("no abstract in the feed; journal articles are never downloaded, so nothing to summarise")
    doc.title_en = raw.title
    doc.authors = list(raw.feed_authors or [])
    doc.published_at = raw.published_at
    doc.abstract_en = abstract if has_abstract(abstract) else None
    doc.paragraphs_en, doc.word_count, doc.content_hash = [], 0, None
    doc.max_level = PublishLevel.summary
    doc.stage = Stage.extracted


def _finish_extract(session: Session, doc: Document) -> None:
    link_authors(session, doc)


def step_extract(session: Session, doc: Document, client: PoliteClient, storage: LocalStorage, settings: Settings) -> None:
    raw = session.get(RawItem, doc.raw_item_id)
    doc.meta = {**(raw.feed_meta or {}), **({"journal": doc.source.name} if doc.source.kind == "journal" else {}),
                **(doc.meta or {})}
    if doc.source.content_mode in ("abstract", "toc") and not doc.item_license:
        _extract_feed_only(doc, raw)
        _finish_extract(session, doc)
        return
    fragment = paragraphs_from_fragment(raw.feed_content) if raw.feed_content else []
    if word_count(fragment) >= FEED_FULLTEXT_WORDS:
        ex = Extracted(title=raw.title, paragraphs=fragment, authors=list(raw.feed_authors or []))
    else:
        ex = _download_and_extract(doc, raw, client, storage)

    abstract = ex.abstract
    if raw.feed_summary:
        summary_text = " ".join(paragraphs_from_fragment(f"<p>{raw.feed_summary}</p>"))
        if len(summary_text.split()) > len((abstract or "").split()):
            abstract = summary_text
    paragraphs = ex.paragraphs if word_count(ex.paragraphs) >= MIN_BODY_WORDS else []
    if not paragraphs and len((abstract or "").split()) < 5:
        raise Insufficient("not enough text to summarise (paywall or empty page)")

    doc.title_en = raw.title or ex.title
    doc.authors = list(raw.feed_authors or []) or ex.authors
    doc.published_at = raw.published_at or ex.published_at
    doc.abstract_en = abstract
    doc.paragraphs_en = paragraphs
    doc.word_count = word_count(paragraphs)
    doc.content_hash = content_hash(paragraphs) if paragraphs else None
    body_text = "\n".join(paragraphs + [abstract or ""])
    doc.max_level = (max_publish_level(doc.source, body_text, settings, doc.item_license)
                     if paragraphs else PublishLevel.summary)

    if doc.content_hash:
        dup = session.scalar(select(Document.id).where(
            Document.content_hash == doc.content_hash, Document.id != doc.id,
            Document.stage.not_in([Stage.failed, Stage.rejected])))
        if dup:
            doc.stage, doc.error = Stage.rejected, f"duplicate of document {dup}"
            return
    _finish_extract(session, doc)
    doc.stage = Stage.extracted


def step_classify(session: Session, doc: Document, llm: LLM, settings: Settings) -> None:
    data, res = classify(llm, doc_input(doc), settings)
    record_usage(session, doc, "classify", res)
    doc.doc_type, doc.importance, doc.keywords = data["doc_type"], data["importance"], data["keywords_en"]
    wanted = [("topic", s) for s in data["topics"]] + [("region", s) for s in data["regions"]] + [("doc_type", data["doc_type"])]
    terms = {(t.kind, t.slug): t for t in session.scalars(select(TaxonomyTerm)).all()}
    doc.tags = [t for t in doc.tags if t.origin == "human"]
    have = {t.term_id for t in doc.tags}
    for key in wanted:
        term = terms.get(key)
        if term and term.id not in have:
            doc.tags.append(DocumentTag(term_id=term.id, origin="ai"))
            have.add(term.id)
    doc.stage = Stage.classified


def _toc_summary(llm: LLM, doc: Document, terms: list[Term], settings: Settings) -> tuple[dict, LLMResult]:
    """Title-only entries (journal tables of contents): translate the title, invent nothing else."""
    title_ar, _, res = translate_one(llm, DocInput(title=doc.title_en, paragraphs=[doc.title_en]), 0, terms, settings)
    empty = {"dek_ar": "", "thesis_ar": "", "key_points_ar": [], "evidence_ar": "", "recommendations_ar": [],
             "significance_ar": "", "quotes": [], "new_terms": []}
    return {**empty, "title_ar": title_ar, "toc_only": True}, res


def step_summarize(session: Session, doc: Document, llm: LLM, terms: list[Term], settings: Settings) -> None:
    if not doc.paragraphs_en and not doc.abstract_en:
        data, res = _toc_summary(llm, doc, terms, settings)
    else:
        data, res = summarize(llm, doc_input(doc), terms, settings)
    record_usage(session, doc, "summarize", res)
    tr = doc.translation or Translation(document_id=doc.id)
    doc.translation = tr
    tr.title_ar = data["title_ar"]
    tr.summary = data
    tr.publish_level = doc.max_level
    tr.model, tr.prompt_version = res.model, PROMPT_VERSION
    tr.cost_usd = (tr.cost_usd or 0) + res.cost_usd
    known = {t.en.lower() for t in terms} | set(
        session.scalars(select(func.lower(GlossaryTerm.term_en))).all())
    for t in data.get("new_terms", []):
        if t["en"].lower() not in known:
            session.add(GlossaryTerm(term_en=t["en"], term_ar=t["ar"], status="proposed", domain="proposed"))
            known.add(t["en"].lower())
    doc.stage = Stage.summarized


def needs_review(doc: Document, tr: Translation, settings: Settings) -> bool:
    if not settings.auto_publish:
        return True
    if (doc.importance or 5) >= settings.review_min_importance:
        return True
    return bool(tr.qa_report.get("high")) or bool(tr.notes)


def step_translate(session: Session, doc: Document, llm: LLM, terms: list[Term], settings: Settings) -> None:
    tr = doc.translation
    if doc.max_level == PublishLevel.full and doc.paragraphs_en:
        result = translate(llm, doc_input(doc), terms, settings, context_ar=tr.summary.get("thesis_ar", ""))
        for res in result.calls:
            record_usage(session, doc, "translate", res)
        tr.paragraphs_ar, tr.notes = result.paragraphs, result.notes
        tr.cost_usd += result.cost_usd
        report, judge = qa_check(doc.paragraphs_en, result.paragraphs, terms, settings, llm)
        if judge:
            record_usage(session, doc, "qa_judge", judge)
            tr.cost_usd += judge.cost_usd
        tr.qa_report = report
    else:
        tr.paragraphs_ar, tr.notes = None, []  # rights level c: never translate the body
        tr.qa_report = {"score": None, "issues": [], "high": 0, "summary_only": True}
    if needs_review(doc, tr, settings):
        doc.stage = Stage.review
    else:
        publish(session, doc, user=None)


# ---------------------------------------------------------------- publishing
def build_search_text(doc: Document, tr: Translation) -> str:
    s = tr.summary or {}
    parts = [tr.title_ar, s.get("dek_ar", ""), s.get("thesis_ar", ""), " ".join(s.get("key_points_ar", []))]
    if tr.publish_level == PublishLevel.full and tr.paragraphs_ar:
        parts.extend(tr.paragraphs_ar)
    latin = " ".join([doc.title_en, " ".join(doc.authors or []), doc.source.name, " ".join(doc.keywords or [])])
    arabic = " ".join(parts)
    # Both the normalised text and its article-stripped form are indexed, so "ردع" finds "الردع".
    return f"{normalize_ar(arabic)} {loose_form(arabic)} {latin.lower()}"


def publish(session: Session, doc: Document, user: User | None) -> None:
    tr = doc.translation
    if tr is None:
        raise ValueError("nothing to publish")
    if tr.publish_level == PublishLevel.full and doc.max_level != PublishLevel.full:
        tr.publish_level = PublishLevel.summary  # rights guard: never exceed the source's level
    tr.published_at = tr.published_at or utcnow()
    tr.human_reviewed = user is not None
    if user is not None:
        tr.reviewer_id, tr.reviewed_at = user.id, utcnow()
    tr.search_text = build_search_text(doc, tr)
    doc.stage = Stage.published
    audit(session, "publish", doc, user, machine_only=user is None)


# ---------------------------------------------------------------- driver
def claim_next(session: Session, stages: tuple[Stage, ...], exclude: set[int] | None = None) -> Document | None:
    query = select(Document).where(Document.stage.in_(stages))
    if exclude:
        query = query.where(Document.id.not_in(exclude))
    return session.scalar(
        query
        .order_by(Document.importance.desc().nulls_last(), Document.created_at)
        .limit(1).with_for_update(skip_locked=True)
    )


def advance(session: Session, doc: Document, *, llm: LLM, client: PoliteClient, storage: LocalStorage,
            settings: Settings, terms: list[Term]) -> Stage:
    doc.error = None
    try:
        if doc.stage == Stage.discovered:
            step_extract(session, doc, client, storage, settings)
        elif doc.stage == Stage.extracted:
            step_classify(session, doc, llm, settings)
        elif doc.stage == Stage.classified:
            step_summarize(session, doc, llm, terms, settings)
        elif doc.stage == Stage.summarized:
            step_translate(session, doc, llm, terms, settings)
    except (LLMRefusal, Insufficient) as exc:
        doc.stage, doc.error = Stage.failed, f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 - one bad document must not stop the worker
        if isinstance(exc, FetchError):
            log.warning("document %s: %s", doc.id, exc)
        else:
            log.exception("document %s failed at %s", doc.id, doc.stage.value)
        doc.attempts += 1
        doc.error = f"{type(exc).__name__}: {exc}"[:2000]
        if doc.attempts >= MAX_ATTEMPTS:
            doc.stage = Stage.failed
    return doc.stage
