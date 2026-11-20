"""PDF text extraction: running headers/footers and footnotes removed, two-column pages read in order."""

import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from marsad.extract.clean import clean_paragraphs
from marsad.extract.types import Extracted

PAGE_NUMBER = re.compile(r"^(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?$", re.I)
SMALL_FONT_RATIO = 0.85
HEADER_MAX_WORDS = 15  # running headers/footers are short; long repeated-looking blocks are body text
TITLE_MAX_WORDS = 25  # blocks clearly smaller than body text are footnotes, captions or page furniture


@dataclass
class Block:
    x0: float
    y0: float
    x1: float
    text: str
    size: float  # dominant font size


def _norm(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def _page_blocks(page) -> list[Block]:
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        lines, sizes = [], Counter()
        for line in b["lines"]:
            text = "".join(span["text"] for span in line["spans"])
            for span in line["spans"]:
                sizes[round(span["size"], 1)] += len(span["text"])
            lines.append(text)
        text = "\n".join(lines).strip()
        if text:
            out.append(Block(b["bbox"][0], b["bbox"][1], b["bbox"][2], text, sizes.most_common(1)[0][0]))
    return out


def reading_order(blocks: list[Block], page_width: float) -> list[Block]:
    """Full-width blocks split the page into bands; inside a band, the left column is read before the right."""
    mid = page_width / 2
    full = sorted((b for b in blocks if b.x1 - b.x0 > page_width * 0.55), key=lambda b: b.y0)
    narrow = [b for b in blocks if b.x1 - b.x0 <= page_width * 0.55]
    ordered: list[Block] = []
    for band in range(len(full) + 1):
        if band > 0:
            ordered.append(full[band - 1])
        top = full[band - 1].y0 if band > 0 else float("-inf")
        bottom = full[band].y0 if band < len(full) else float("inf")
        inside = [b for b in narrow if top <= b.y0 < bottom]
        left = sorted((b for b in inside if b.x0 < mid), key=lambda b: b.y0)
        right = sorted((b for b in inside if b.x0 >= mid), key=lambda b: b.y0)
        ordered.extend(left + right)
    return ordered


def extract_pdf(data: bytes) -> Extracted:
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages = [(reading_order(_page_blocks(page), page.rect.width)) for page in doc]

    sizes = Counter()
    for blocks in pages:
        for b in blocks:
            sizes[b.size] += len(b.text)
    body_size = sizes.most_common(1)[0][0] if sizes else 0

    # A block that repeats (digits ignored) on more than half the pages is a running header/footer.
    counts = Counter(_norm(b.text) for blocks in pages for b in {x.text: x for x in blocks}.values()
                     if len(b.text.split()) <= HEADER_MAX_WORDS)
    threshold = max(2, len(pages) // 2 + 1) if len(pages) > 2 else 99
    repeated = {k for k, v in counts.items() if v >= threshold}

    paragraphs: list[str] = []
    for blocks in pages:
        for block in blocks:
            if _norm(block.text) in repeated or PAGE_NUMBER.match(block.text.strip()):
                continue
            if body_size and block.size < body_size * SMALL_FONT_RATIO:
                continue
            text = re.sub(r"(\w)-\n(\w)", r"\1\2", block.text)  # de-hyphenate line breaks
            text = re.sub(r"\s*\n\s*", " ", text).strip()
            # A block that starts lowercase continues the previous paragraph (page or column break).
            if paragraphs and text and text[0].islower() and not paragraphs[-1].endswith((".", "?", "!", ":")):
                paragraphs[-1] = f"{paragraphs[-1]} {text}"
            else:
                paragraphs.append(text)

    meta = doc.metadata or {}
    title = (meta.get("title") or "").strip()
    authors = [a.strip() for a in re.split(r";|,| and ", meta.get("author") or "") if a.strip()]
    paragraphs = clean_paragraphs(paragraphs)
    if not title and paragraphs and len(paragraphs[0].split()) <= TITLE_MAX_WORDS:
        title = paragraphs.pop(0)
    return Extracted(title=title, paragraphs=paragraphs, authors=authors)
