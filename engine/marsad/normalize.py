"""URL canonicalisation and content fingerprints."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "_hsenc", "_hsmi", "igshid"}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"
    host = parts.netloc.lower()
    if host.endswith(":443"):
        host = host[:-4]
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((scheme, host, path, urlencode(sorted(query)), ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()


def content_hash(paragraphs: list[str]) -> str:
    text = " ".join(re.sub(r"\W+", " ", p.lower()).strip() for p in paragraphs)
    return hashlib.sha256(text.encode()).hexdigest()


def word_count(paragraphs: list[str]) -> int:
    return sum(len(p.split()) for p in paragraphs)
