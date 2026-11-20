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


def find_pdf_link(html: str, base_url: str) -> str | None:
    """The full report behind a landing page: citation_pdf_url meta tag, else a 'PDF' / 'Download' link to a .pdf."""
    from urllib.parse import urljoin, urlsplit

    tree = LexborHTMLParser(html)
    meta = tree.css_first('meta[name="citation_pdf_url"]')
    if meta is not None and meta.attributes.get("content"):
        return urljoin(base_url, meta.attributes["content"])
    host = urlsplit(base_url).netloc
    for a in tree.css("a[href]"):
        href = a.attributes.get("href") or ""
        url = urljoin(base_url, href)
        label = (a.text(strip=True) + " " + (a.attributes.get("title") or "")).lower()
        if urlsplit(url).path.lower().endswith(".pdf") and urlsplit(url).netloc == host and (
                "pdf" in label or "download" in label or "full" in label):
            return url
    return None
