"""Journal metadata from feeds and abstract clean-up (strategy plan 2: journal rows)."""

import re

from selectolax.lexbor import LexborHTMLParser

DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>&]+)", re.I)
OPEN_ACCESS = re.compile(r"\bopen[ -]access\b", re.I)
# Citation boilerplate T&F / MIT Press put in front of the abstract, e.g.
# "Volume 41, Issue 6, December 2026, Page 812-835." or "Ahead of Print."
CITATION_WITH_PAGES = re.compile(r"^\s*(?:Ahead of Print\.?\s*)?Volume\s+\d+.*?Pages?\s+[\w\-–]+\.?\s*", re.I)
CITATION_TO_PERIOD = re.compile(r"^\s*(?:Ahead of Print\.?\s*)?(?:Volume\s+\d+[^.]*\.\s*)?", re.I)
MIN_ABSTRACT_WORDS = 30


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    tree = LexborHTMLParser(f"<div>{html}</div>")
    for node in tree.css("img, script, style"):
        node.decompose()
    return re.sub(r"\s+", " ", tree.body.text(separator=" ") if tree.body else "").strip()


def clean_abstract(html: str | None) -> str:
    text = html_to_text(html)
    stripped = CITATION_WITH_PAGES.sub("", text, count=1)
    text = (stripped if stripped != text else CITATION_TO_PERIOD.sub("", text, count=1)).strip()
    text = re.sub(r"^(abstract|summary)\s*[:.]?\s*", "", text, flags=re.I)
    return text


def has_abstract(text: str) -> bool:
    return len(text.split()) >= MIN_ABSTRACT_WORDS


def feed_meta(entry: dict, text_fields: str) -> dict:
    """entry is a feedparser entry; text_fields is concatenated description/content used for DOI/OA hints."""
    meta: dict = {}
    for key, out in (("prism_volume", "volume"), ("prism_number", "issue"), ("prism_issue", "issue"),
                     ("prism_startingpage", "start_page"), ("prism_endingpage", "end_page"),
                     ("prism_publicationname", "journal")):
        if entry.get(key):
            meta[out] = str(entry[key]).strip()
    if "volume" not in meta or "issue" not in meta:
        m = re.search(r"Volume\s+(\d+)\s*,\s*Issue\s+(\d+)", text_fields, re.I)
        if m:
            meta.setdefault("volume", m.group(1))
            meta.setdefault("issue", m.group(2))
    if "start_page" not in meta:
        m = re.search(r"Pages?\s+(\d+)\s*[-–]\s*(\d+)", text_fields, re.I)
        if m:
            meta["start_page"], meta["end_page"] = m.group(1), m.group(2)
    for candidate in (entry.get("prism_doi"), entry.get("dc_identifier"), entry.get("id"), entry.get("link"), text_fields):
        m = DOI.search(str(candidate or ""))
        if m:
            meta["doi"] = m.group(1).rstrip(".,;)")
            break
    tags = " ".join(t.get("term", "") for t in entry.get("tags", []) or [])
    if OPEN_ACCESS.search(f"{tags} {text_fields} {entry.get('title', '')}"):
        meta["open_access"] = True
    return meta
