"""Fetch one source and register newly discovered items."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.fetch.entries import Entry
from marsad.fetch.http import FetchError, PoliteClient
from marsad.fetch.listing import parse_listing
from marsad.fetch.rss import parse_feed
from marsad.models import Document, RawItem, Source, Stage
from marsad.normalize import url_hash

log = logging.getLogger(__name__)


def due_sources(session: Session, now: datetime | None = None) -> list[Source]:
    now = now or datetime.now(timezone.utc)
    sources = session.scalars(
        select(Source).where(Source.is_active, Source.fetch_method != "none", Source.feed_url.is_not(None))
    ).all()
    return [
        s for s in sources
        if s.last_fetched_at is None or s.last_fetched_at + timedelta(minutes=s.fetch_interval_min) <= now
    ]


def _entries(source: Source, client: PoliteClient) -> list[Entry] | None:
    result = client.get(source.feed_url, etag=source.etag, last_modified=source.last_modified)
    if result.not_modified:
        return None
    source.etag = result.headers.get("etag")
    source.last_modified = result.headers.get("last-modified")
    if source.fetch_method == "rss":
        return parse_feed(result.content)
    return parse_listing(result.content.decode("utf-8", "replace"), result.url, source.listing_config or {})


def register_entries(session: Session, source: Source, entries: list[Entry]) -> int:
    hashes: dict[str, Entry] = {}
    for e in entries:  # first occurrence wins: later duplicates usually carry less metadata
        hashes.setdefault(url_hash(e.url), e)
    if not hashes:
        return 0
    existing = set(session.scalars(select(RawItem.url_hash).where(RawItem.url_hash.in_(hashes))).all())
    new = 0
    for h, e in hashes.items():
        if h in existing:
            continue
        raw = RawItem(source_id=source.id, url=e.url, url_hash=h, title=e.title, published_at=e.published_at,
                      feed_content=e.content_html, feed_summary=e.summary, feed_authors=e.authors,
                      feed_meta=e.meta)
        session.add(raw)
        session.flush()
        session.add(Document(source_id=source.id, raw_item_id=raw.id, url=e.url, title_en=e.title,
                             published_at=e.published_at, authors=e.authors, stage=Stage.discovered))
        new += 1
    return new


def fetch_source(session: Session, source: Source, client: PoliteClient) -> int:
    source.last_fetched_at = datetime.now(timezone.utc)
    try:
        entries = _entries(source, client)
        new = 0 if entries is None else register_entries(session, source, entries)
    except (FetchError, ValueError) as exc:
        source.last_error = str(exc)[:2000]
        log.warning("fetch failed for %s: %s", source.slug, exc)
        session.commit()
        return 0
    source.last_error = None
    source.last_success_at = source.last_fetched_at
    session.commit()
    log.info("fetched %s: %d new", source.slug, new)
    return new
