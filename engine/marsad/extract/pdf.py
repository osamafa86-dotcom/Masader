"""PDF text extraction with header/footer removal and paragraph rebuilding."""

import re
from collections import Counter

import pymupdf

from marsad.extract.clean import clean_paragraphs
from marsad.extract.types import Extracted

PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.I)


def _norm(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def extract_pdf(data: bytes) -> Extracted:
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages: list[list[str]] = []
    for page in doc:
        blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1]), b[0]))
        pages.append([b[4] for b in blocks if b[6] == 0 and b[4].strip()])

    # A block that repeats (digits ignored) on more than half the pages is a running header/footer.
    counts = Counter(_norm(b) for blocks in pages for b in set(blocks))
    threshold = max(2, len(pages) // 2 + 1) if len(pages) > 2 else 99
    repeated = {k for k, v in counts.items() if v >= threshold}

    paragraphs: list[str] = []
    for blocks in pages:
        for block in blocks:
            if _norm(block) in repeated or PAGE_NUMBER.match(block.strip()):
                continue
            text = re.sub(r"(\w)-\n(\w)", r"\1\2", block)  # de-hyphenate line breaks
            text = re.sub(r"\s*\n\s*", " ", text).strip()
            # A block that starts lowercase continues the previous paragraph across a page break.
            if paragraphs and text and text[0].islower() and not paragraphs[-1].endswith((".", "?", "!", ":")):
                paragraphs[-1] = f"{paragraphs[-1]} {text}"
            else:
                paragraphs.append(text)

    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    authors = [a.strip() for a in re.split(r";|,| and ", meta.get("author") or "") if a.strip()]
    paragraphs = clean_paragraphs(paragraphs)
    if not title and paragraphs:
        title = paragraphs.pop(0)
    return Extracted(title=title, paragraphs=paragraphs, authors=authors)
