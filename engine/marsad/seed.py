"""Idempotent seeding of sources, taxonomy and the starter glossary."""

from importlib import resources

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.models import GlossaryTerm, RightsLevel, Source, TaxonomyTerm


def _load(name: str):
    return yaml.safe_load(resources.files("marsad.data").joinpath(name).read_text(encoding="utf-8"))


SOURCE_FIELDS = (
    "name", "name_ar", "homepage", "kind", "description_ar", "fetch_method", "feed_url",
    "listing_config", "fetch_interval_min", "license", "rights_evidence",
    "per_item_copyright_check", "is_active", "content_mode", "language",
)


def seed_sources(session: Session) -> int:
    count = 0
    for row in _load("sources.yaml"):
        src = session.scalar(select(Source).where(Source.slug == row["slug"]))
        if src is None:
            src = Source(slug=row["slug"])
            session.add(src)
            # Rights and activation are editorial decisions: set only on first insert,
            # never overwritten by a re-seed.
            src.rights_level = RightsLevel(row.get("rights_level", "c"))
            src.is_active = bool(row.get("is_active", False))
        for field in SOURCE_FIELDS:
            if field in ("is_active",):
                continue
            default = {} if field == "listing_config" else (False if field == "per_item_copyright_check" else None)
            value = row.get(field, default)
            if field == "description_ar" and value is None:
                value = ""
            if field == "rights_evidence" and value is None:
                value = ""
            if field == "fetch_interval_min" and value is None:
                value = 60
            if field == "content_mode" and value is None:
                value = "full"
            if field == "language" and value is None:
                value = "en"
            setattr(src, field, value)
        count += 1
    session.flush()
    return count


def seed_taxonomy(session: Session) -> int:
    count = 0
    for kind, terms in _load("taxonomy.yaml").items():
        for slug, (name_ar, name_en) in terms.items():
            term = session.scalar(select(TaxonomyTerm).where(TaxonomyTerm.kind == kind, TaxonomyTerm.slug == slug))
            if term is None:
                term = TaxonomyTerm(kind=kind, slug=slug)
                session.add(term)
            term.name_ar, term.name_en = name_ar, name_en
            count += 1
    session.flush()
    return count


def seed_glossary(session: Session) -> int:
    count = 0
    lists = {"en": _load("glossary.yaml"), **_load("glossary_multilingual.yaml")}
    for lang, terms in lists.items():
        for term, (term_ar, domain, variants) in terms.items():
            existing = session.scalar(select(GlossaryTerm).where(GlossaryTerm.lang == lang, GlossaryTerm.term_en == term))
            if existing is None:  # never overwrite an editor's later correction
                session.add(GlossaryTerm(lang=lang, term_en=term, term_ar=term_ar, domain=domain,
                                         variants_ar=variants or []))
            count += 1
    session.flush()
    return count


def seed_all(session: Session) -> dict[str, int]:
    return {
        "sources": seed_sources(session),
        "taxonomy": seed_taxonomy(session),
        "glossary": seed_glossary(session),
    }
