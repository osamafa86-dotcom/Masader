"""Turning ORM rows into the JSON shapes the web app consumes. Rights rules are applied here."""

from marsad.ai.glossary import relevant_terms, Term
from marsad.models import Document, GlossaryTerm, PublishLevel, Source, Translation
from marsad.citations import all_citations
from marsad.rights import rights_note


def source_brief(s: Source) -> dict:
    return {"slug": s.slug, "name": s.name, "name_ar": s.name_ar, "homepage": s.homepage, "kind": s.kind}


def _tags(doc: Document, kind: str) -> list[dict]:
    return [{"slug": t.term.slug, "name_ar": t.term.name_ar} for t in doc.tags if t.term.kind == kind]


def effective_level(doc: Document, tr: Translation) -> PublishLevel:
    """The level actually served: never above what the source's rights allow today."""
    if tr.publish_level == PublishLevel.full and doc.max_level == PublishLevel.full and tr.paragraphs_ar:
        return PublishLevel.full
    return PublishLevel.summary


META_KEYS = ("journal", "volume", "issue", "start_page", "end_page", "doi", "open_access")


def summary_basis(doc: Document, tr: Translation) -> str:
    """What the Arabic summary rests on: the full text, the published abstract, or the title only."""
    if (tr.summary or {}).get("toc_only"):
        return "title"
    return "full_text" if doc.paragraphs_en else "abstract"


def article_card(doc: Document) -> dict:
    tr = doc.translation
    doc_types = _tags(doc, "doc_type")
    return {
        "id": doc.id,
        "title_ar": tr.title_ar,
        "title_en": doc.title_en,
        "dek_ar": (tr.summary or {}).get("dek_ar", ""),
        "source": source_brief(doc.source),
        "authors": doc.authors or [],
        "authors_detail": [{"name": link.author.name, "slug": link.author.slug} for link in doc.author_links],
        "original_published_at": doc.published_at.isoformat() if doc.published_at else None,
        "published_at": tr.published_at.isoformat() if tr.published_at else None,
        "publish_level": effective_level(doc, tr).value,
        "human_reviewed": tr.human_reviewed,
        "topics": _tags(doc, "topic"),
        "regions": _tags(doc, "region"),
        "doc_type": doc_types[0] if doc_types else None,
        "importance": doc.importance,
        "url": doc.url,
        "word_count": doc.word_count,
        "basis": summary_basis(doc, tr),
        "source_language": doc.language or "en",
        "meta": {k: (doc.meta or {}).get(k) for k in META_KEYS if (doc.meta or {}).get(k)},
    }


def citation(doc: Document) -> str:
    authors = ", ".join(doc.authors or []) or doc.source.name
    year = doc.published_at.year if doc.published_at else "n.d."
    return f"{authors} ({year}). {doc.title_en}. {doc.source.name}. {doc.url}"


def article_detail(doc: Document, glossary: list[GlossaryTerm], site_name: str = "مرصد",
                   site_url: str = "") -> dict:
    tr = doc.translation
    level = effective_level(doc, tr)
    s = tr.summary or {}
    body = None
    if level == PublishLevel.full:
        body = [{"en": en, "ar": ar} for en, ar in zip(doc.paragraphs_en, tr.paragraphs_ar)]
    text = "\n".join([doc.title_en, doc.abstract_en or ""] + list(doc.paragraphs_en or []))
    terms = {t.term_en: t for t in glossary}
    used = relevant_terms(text, [Term(t.term_en, t.term_ar) for t in glossary])
    return {
        **article_card(doc),
        "summary": {k: s.get(k) for k in ("thesis_ar", "key_points_ar", "evidence_ar", "recommendations_ar",
                                           "significance_ar", "quotes")},
        "body": body,
        "license": (doc.item_license or doc.source.license) if level == PublishLevel.full else None,
        "rights_note": rights_note(doc.source, level, doc.item_license),
        "glossary": [{"en": t.en, "ar": t.ar, "definition_ar": terms[t.en].definition_ar} for t in used][:30],
        "translation": {"model": tr.model, "prompt_version": tr.prompt_version,
                        "reviewed_at": tr.reviewed_at.isoformat() if tr.reviewed_at else None},
        "citation_original": citation(doc),
        "citations": all_citations(doc, site_name, site_url),
    }


def editor_item(doc: Document) -> dict:
    tr = doc.translation
    return {
        "id": doc.id,
        "stage": doc.stage.value,
        "error": doc.error,
        "attempts": doc.attempts,
        "title_en": doc.title_en,
        "url": doc.url,
        "authors": doc.authors or [],
        "source": {**source_brief(doc.source), "rights_level": doc.source.rights_level.value,
                   "license": doc.source.license},
        "original_published_at": doc.published_at.isoformat() if doc.published_at else None,
        "created_at": doc.created_at.isoformat(),
        "importance": doc.importance,
        "doc_type": doc.doc_type,
        "max_level": doc.max_level.value,
        "word_count": doc.word_count,
        "abstract_en": doc.abstract_en,
        "meta": doc.meta or {},
        "item_license": doc.item_license,
        "item_rights_evidence": doc.item_rights_evidence,
        "content_mode": doc.source.content_mode,
        "source_language": doc.language or "en",
        "paragraphs_en": doc.paragraphs_en or [],
        "topics": _tags(doc, "topic"),
        "regions": _tags(doc, "region"),
        "translation": None if tr is None else {
            "title_ar": tr.title_ar,
            "summary": tr.summary,
            "paragraphs_ar": tr.paragraphs_ar,
            "notes": tr.notes,
            "publish_level": tr.publish_level.value,
            "qa_report": tr.qa_report,
            "cost_usd": round(tr.cost_usd or 0, 4),
            "model": tr.model,
            "human_reviewed": tr.human_reviewed,
            "published_at": tr.published_at.isoformat() if tr.published_at else None,
        },
    }


def queue_row(doc: Document) -> dict:
    tr = doc.translation
    return {
        "id": doc.id,
        "stage": doc.stage.value,
        "title_en": doc.title_en,
        "title_ar": tr.title_ar if tr else None,
        "source": source_brief(doc.source),
        "importance": doc.importance,
        "max_level": doc.max_level.value,
        "qa_score": (tr.qa_report or {}).get("score") if tr else None,
        "qa_high": (tr.qa_report or {}).get("high", 0) if tr else 0,
        "notes": len(tr.notes or []) if tr else 0,
        "error": doc.error,
        "created_at": doc.created_at.isoformat(),
    }
