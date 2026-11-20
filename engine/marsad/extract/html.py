"""HTML article extraction (trafilatura for full pages, lexbor for feed fragments)."""

from datetime import datetime, timezone

import trafilatura
from selectolax.lexbor import LexborHTMLParser

from marsad.extract.clean import clean_paragraphs
from marsad.extract.types import Extracted

BLOCK_TAGS = "p, h2, h3, h4, li, blockquote"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def paragraphs_from_fragment(html: str) -> list[str]:
    tree = LexborHTMLParser(html)
    blocks = []
    for node in tree.css(BLOCK_TAGS):
        # skip <p> nested inside <li>/<blockquote> to avoid double counting
        if node.tag == "p" and node.parent is not None and node.parent.tag in ("li", "blockquote"):
            continue
        blocks.append(node.text(separator=" ", strip=True))
    return clean_paragraphs(blocks)


def extract_html(html: str, url: str) -> Extracted:
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False,
                               favor_precision=True, output_format="txt")
    paragraphs = clean_paragraphs(text.split("\n")) if text else []
    meta = trafilatura.extract_metadata(html, default_url=url)
    authors: list[str] = []
    title = ""
    published = None
    abstract = None
    if meta is not None:
        title = meta.title or ""
        if meta.author:
            authors = [a.strip() for a in meta.author.replace(" and ", ";").split(";") if a.strip()]
        published = _parse_date(meta.date)
        abstract = meta.description
    if paragraphs and title and paragraphs[0] == title:
        paragraphs = paragraphs[1:]
    return Extracted(title=title, paragraphs=paragraphs, authors=authors, published_at=published, abstract=abstract)
