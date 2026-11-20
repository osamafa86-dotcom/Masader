"""RSS/Atom parsing."""

import calendar
from datetime import datetime, timezone

import feedparser

from marsad.fetch.entries import Entry


def _date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return None


def parse_feed(content: bytes) -> list[Entry]:
    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"not a feed: {feed.bozo_exception}")
    entries = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        content_html = None
        if e.get("content"):
            content_html = max((c.get("value", "") for c in e.content), key=len) or None
        authors = [a.get("name") for a in e.get("authors", []) if a.get("name")]
        if not authors and e.get("author"):
            authors = [e.author]
        entries.append(Entry(url=link, title=e.get("title", "").strip(), published_at=_date(e),
                             content_html=content_html, summary=e.get("summary"), authors=authors))
    return entries
