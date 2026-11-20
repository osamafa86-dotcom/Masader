"""HTTP client that respects robots.txt, per-host delays and conditional GET."""

import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from marsad.config import Settings


class FetchError(Exception):
    pass


class RobotsDisallowed(FetchError):
    pass


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def not_modified(self) -> bool:
        return self.status == 304

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()


class PoliteClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self.settings = settings
        self.user_agent = settings.resolved_user_agent()
        self._client = httpx.Client(
            headers={"User-Agent": self.user_agent, "Accept-Language": "en"},
            timeout=settings.http_timeout_s,
            follow_redirects=True,
            transport=transport,
        )
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._sleep = sleep

    def close(self) -> None:
        self._client.close()

    def _wait_turn(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            remaining = self.settings.per_host_delay_s - (time.monotonic() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_hit[host] = time.monotonic()

    def _robots_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = None
            try:
                self._wait_turn(parts.netloc)
                resp = self._client.get(f"{origin}/robots.txt")
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
            except httpx.HTTPError:
                parser = None  # unreachable robots.txt: treat as no restrictions
            self._robots[origin] = parser
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        robots = self._robots_for(url)
        return robots is None or robots.can_fetch(self.user_agent, url)

    def get(self, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        if not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        self._wait_turn(urlsplit(url).netloc)
        try:
            resp = self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise FetchError(f"{type(exc).__name__}: {exc}") from exc
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code} for {url}")
        return FetchResult(url=str(resp.url), status=resp.status_code, content=resp.content,
                           headers={k.lower(): v for k, v in resp.headers.items()})
