"""Discovery of article links from a listing page, for sources without a feed."""

import re
from urllib.parse import urljoin

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from marsad.fetch.entries import Entry
from marsad.normalize import canonical_url


def parse_listing(html: str, base_url: str, cfg: dict) -> list[Entry]:
    tree = HTMLParser(html)
    pattern = re.compile(cfg.get("link_pattern", "."))
    seen: set[str] = set()
    entries: list[Entry] = []
    containers = tree.css(cfg.get("item_selector", "body")) or [tree.body]
    for node in containers:
        if node is None:
            continue
        for a in node.css(cfg.get("link_selector", "a[href]")):
            href = a.attributes.get("href")
            if not href:
                continue
            url = urljoin(base_url, href)
            if not pattern.search(url):
                continue
            key = canonical_url(url)
            if key in seen or key == canonical_url(base_url):
                continue
            seen.add(key)
            entries.append(Entry(url=url, title=a.text(strip=True)))
    return entries
