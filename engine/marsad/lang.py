"""Lightweight language identification for the languages Marsad monitors (script first, then stopwords)."""

import re

SCRIPTS = {
    "ar": re.compile(r"[؀-ۿ]"),
    "he": re.compile(r"[֐-׿]"),
    "ru": re.compile(r"[Ѐ-ӿ]"),
    "zh": re.compile(r"[一-鿿]"),
    "latin": re.compile(r"[A-Za-zÀ-ÿ]"),
}
STOPWORDS = {
    "en": {"the", "and", "of", "to", "in", "is", "that", "for", "with", "on", "as", "are", "this", "by"},
    "fr": {"le", "la", "les", "des", "et", "du", "une", "est", "dans", "que", "pour", "qui", "sur", "pas"},
    "de": {"der", "die", "das", "und", "nicht", "mit", "ist", "den", "von", "zu", "auf", "ein", "eine", "dem"},
    "es": {"el", "los", "las", "del", "y", "que", "en", "una", "por", "con", "para", "es", "como", "se"},
}
NAMES = {"en": "الإنجليزية", "fr": "الفرنسية", "de": "الألمانية", "es": "الإسبانية", "ru": "الروسية",
         "he": "العبرية", "zh": "الصينية", "ar": "العربية"}
RTL = {"ar", "he"}


def detect(text: str, default: str = "en") -> str:
    sample = text[:5000]
    counts = {k: len(p.findall(sample)) for k, p in SCRIPTS.items()}
    letters = sum(counts.values())
    if not letters:
        return default
    script = max(counts, key=counts.get)
    if script != "latin":
        return script if counts[script] / letters > 0.3 else default
    words = re.findall(r"[a-zà-ÿ]+", sample.lower())
    scores = {lang: sum(1 for w in words if w in sw) for lang, sw in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 3 else default


def script_of(lang: str) -> re.Pattern:
    return SCRIPTS.get(lang, SCRIPTS["latin"])
