from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Extracted:
    title: str = ""
    paragraphs: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    published_at: datetime | None = None
    abstract: str | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)
