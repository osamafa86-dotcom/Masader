from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Entry:
    url: str
    title: str = ""
    published_at: datetime | None = None
    content_html: str | None = None
    summary: str | None = None
    authors: list[str] = field(default_factory=list)
