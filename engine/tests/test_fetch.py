from sqlalchemy import func, select

from marsad.fetch.http import PoliteClient
from marsad.fetch.listing import parse_listing
from marsad.fetch.run import due_sources, fetch_source
from marsad.models import Document, RawItem, Stage
from marsad.normalize import canonical_url
from tests.helpers import make_source, mock_transport

FEED = "https://example-review.test/feed/"


def test_canonical_url_strips_tracking_and_trailing_slash():
    a = canonical_url("http://Example-Review.test/2026/11/x/?utm_source=rss&b=2&a=1#top")
    b = canonical_url("https://example-review.test/2026/11/x?a=1&b=2")
    assert a == b == "https://example-review.test/2026/11/x?a=1&b=2"


def test_feed_registers_new_items_once(db, settings, fixture_bytes):
    src = make_source(db)
    client = PoliteClient(settings, transport=mock_transport({FEED: (200, fixture_bytes("feed.xml"))}))

    assert fetch_source(db, src, client) == 3  # 4 entries, one is a utm/trailing-slash duplicate
    assert fetch_source(db, src, client) == 0
    assert db.scalar(select(func.count()).select_from(RawItem)) == 3

    doc = db.scalar(select(Document).where(Document.title_en.like("Deterrence%")))
    assert doc.stage == Stage.discovered
    assert doc.authors == ["Jane Analyst"]
    raw = db.get(RawItem, doc.raw_item_id)
    assert "deterrence by denial" in raw.feed_content
    assert src.last_error is None and src.last_success_at is not None


def test_server_error_is_recorded_and_not_raised(db, settings):
    src = make_source(db)
    client = PoliteClient(settings, transport=mock_transport({FEED: (500, "boom")}))
    assert fetch_source(db, src, client) == 0
    assert "HTTP 500" in src.last_error
    assert src.last_fetched_at is not None


def test_not_modified_keeps_state(db, settings, fixture_bytes):
    src = make_source(db, etag='"v1"')
    client = PoliteClient(settings, transport=mock_transport({FEED: (304, b"")}))
    assert fetch_source(db, src, client) == 0
    assert src.last_error is None


def test_robots_disallow_blocks_request(db, settings, fixture_bytes):
    src = make_source(db)
    calls: list[str] = []
    routes = {
        "https://example-review.test/robots.txt": (200, "User-agent: *\nDisallow: /feed/\n"),
        FEED: (200, fixture_bytes("feed.xml")),
    }
    client = PoliteClient(settings, transport=mock_transport(routes, calls))
    assert fetch_source(db, src, client) == 0
    assert FEED not in calls
    assert "robots.txt" in src.last_error


def test_per_host_delay_is_applied(settings, fixture_bytes):
    settings.per_host_delay_s = 5.0
    slept: list[float] = []
    client = PoliteClient(settings, transport=mock_transport({FEED: (200, fixture_bytes("feed.xml"))}),
                          sleep=slept.append)
    client.get(FEED)
    client.get(FEED)
    assert slept and all(0 < s <= 5.0 for s in slept)


def test_listing_discovery(fixture_bytes):
    cfg = {"item_selector": ".views-row", "link_selector": "a[href]", "link_pattern": "/research/"}
    entries = parse_listing(fixture_bytes("listing.html").decode(), "https://isw.test/research/", cfg)
    assert [e.url for e in entries] == [
        "https://isw.test/research/russia-ukraine/assessment-november-18-2026",
        "https://isw.test/research/middle-east/iran-update-november-17-2026",
    ]


def test_due_sources_respects_interval(db):
    from datetime import datetime, timedelta, timezone
    src = make_source(db, fetch_interval_min=60)
    now = datetime.now(timezone.utc)
    assert due_sources(db, now) == [src]
    src.last_fetched_at = now - timedelta(minutes=10)
    assert due_sources(db, now) == []
