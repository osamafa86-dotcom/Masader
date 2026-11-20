"""Selecting and formatting glossary terms relevant to a text."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    en: str
    ar: str
    variants: tuple[str, ...] = ()


def _pattern(term: str) -> re.Pattern:
    flags = 0 if term.isupper() else re.IGNORECASE
    return re.compile(rf"(?<![\w-]){re.escape(term)}(?:s|es)?(?![\w-])", flags)


_cache: dict[str, re.Pattern] = {}


def term_in(term: str, text: str) -> bool:
    pat = _cache.get(term)
    if pat is None:
        pat = _cache[term] = _pattern(term)
    return bool(pat.search(text))


def relevant_terms(text: str, terms: list[Term]) -> list[Term]:
    found = [t for t in terms if term_in(t.en, text)]
    # Prefer longer terms first so "deterrence by denial" is listed before "deterrence".
    return sorted(found, key=lambda t: -len(t.en))


def as_prompt(terms: list[Term]) -> list[dict]:
    return [{"en": t.en, "ar": t.ar} for t in terms]
