"""Author records linked to documents, for author pages."""

import re

from slugify import slugify
from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.models import Author, Document, DocumentAuthor

HONORIFICS = re.compile(r"^(dr|prof|professor|gen|general|col|colonel|lt|maj|adm|ambassador|amb|mr|ms|mrs)\.?\s+", re.I)


def split_names(raw: list[str]) -> list[str]:
    """Feeds sometimes put several authors in one field: "Jane Doe and John Roe", "Doe, Roe and Poe"."""
    names: list[str] = []
    for item in raw:
        item = re.sub(r"^\s*by\s+", "", item or "", flags=re.I).strip()
        if not item:
            continue
        listed = re.search(r"\s(and|&)\s|;", item)
        if not listed and item.count(",") == 1 and len(item.split()) <= 4:
            names.append(item)  # "Doe, Jane": one person written surname first
            continue
        names.extend(p for p in re.split(r"\s*(?:,\s*and\s+|\s+and\s+|\s*&\s*|;|,)\s*", item) if p.strip())
    cleaned: list[str] = []
    for n in names:
        n = n.strip()
        while HONORIFICS.match(n):  # "Lt. Col. Sam Hill" carries two
            n = HONORIFICS.sub("", n, count=1)
        n = n.strip(" .")
        if n and n not in cleaned and len(n) <= 200:
            cleaned.append(n)
    return cleaned


def link_authors(session: Session, doc: Document) -> None:
    names = split_names(list(doc.authors or []))
    doc.authors = names
    links: list[DocumentAuthor] = []
    for pos, name in enumerate(names):
        slug = slugify(name)[:200]
        if not slug:
            continue
        author = session.scalar(select(Author).where(Author.slug == slug))
        if author is None:
            author = Author(slug=slug, name=name)
            session.add(author)
            session.flush()
        if all(link.author_id != author.id for link in links):
            links.append(DocumentAuthor(author_id=author.id, position=pos))
    doc.author_links = links
