import httpx

from marsad.models import RightsLevel, Source


def mock_transport(routes: dict[str, tuple[int, bytes | str, dict] | tuple[int, bytes | str]], calls: list | None = None):
    """Map exact URL -> (status, body[, headers]). robots.txt defaults to 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if calls is not None:
            calls.append(url)
        if url in routes:
            status, body, *rest = routes[url]
            headers = rest[0] if rest else {}
            return httpx.Response(status, content=body.encode() if isinstance(body, str) else body, headers=headers)
        if url.endswith("/robots.txt"):
            return httpx.Response(404)
        return httpx.Response(404, content=b"not found")

    return httpx.MockTransport(handler)


def make_source(db, slug="example", rights=RightsLevel.a, method="rss", feed_url="https://example-review.test/feed/",
                **kw) -> Source:
    src = Source(slug=slug, name=slug.title(), name_ar="مصدر تجريبي", homepage="https://example-review.test",
                 kind="media", fetch_method=method, feed_url=feed_url, rights_level=rights, is_active=True, **kw)
    db.add(src)
    db.commit()
    return src
