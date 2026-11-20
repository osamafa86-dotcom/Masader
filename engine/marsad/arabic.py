"""Arabic text normalisation for search and terminology matching."""

import re

DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
TRANSLATE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
    "٬": ",", "٫": ".", "،": ",", "؛": ";", "؟": "?",
})


def normalize_ar(text: str) -> str:
    text = DIACRITICS.sub("", text or "")
    text = text.translate(TRANSLATE).lower()
    return re.sub(r"\s+", " ", text).strip()


def strip_article(word: str) -> str:
    """Remove the definite article and common one-letter prefixes for loose term matching."""
    for prefix in ("وال", "بال", "كال", "فال", "لل", "ال"):
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            return word[len(prefix):]
    return word


def loose_form(text: str) -> str:
    return " ".join(strip_article(w) for w in normalize_ar(text).split())
