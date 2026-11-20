"""Citation strings for the original work (APA 7, Chicago author-date, BibTeX) and for the Arabic translation."""

import re

from marsad.models import Document

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def _split(name: str) -> tuple[str, str]:
    """Return (given, family). Accepts "Jane Q. Analyst" and "Analyst, Jane Q."."""
    if "," in name:
        family, given = [p.strip() for p in name.split(",", 1)]
        return given, family
    parts = name.split()
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _initials(given: str) -> str:
    return " ".join(f"{p[0]}." for p in re.split(r"[\s\-]+", given) if p and p[0].isalpha())


def _apa_names(names: list[str]) -> str:
    formatted = [f"{f}, {_initials(g)}".strip(", ") for g, f in map(_split, names)]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]
    return ", ".join(formatted[:19]) + ", . . . " + formatted[-1]


def _chicago_names(names: list[str]) -> str:
    if not names:
        return ""
    g0, f0 = _split(names[0])
    first = f"{f0}, {g0}".strip(", ")
    rest = names[1:]
    if not rest:
        return first
    if len(rest) == 1:
        return f"{first}, and {rest[0]}"
    return f"{first}, " + ", ".join(rest[:-1]) + f", and {rest[-1]}"


def _pages(meta: dict, sep: str) -> str:
    start, end = meta.get("start_page"), meta.get("end_page")
    if start and end and end != start:
        return f"{start}{sep}{end}"
    return start or ""


def _link(doc: Document) -> str:
    doi = (doc.meta or {}).get("doi")
    return f"https://doi.org/{doi}" if doi else doc.url


def apa(doc: Document) -> str:
    m = doc.meta or {}
    authors = _apa_names(doc.authors) if doc.authors else doc.source.name
    if doc.published_at is None:
        date = "n.d."
    elif m.get("journal") or doc.source.kind == "journal":
        date = str(doc.published_at.year)
    else:
        date = f"{doc.published_at.year}, {MONTHS[doc.published_at.month - 1]} {doc.published_at.day}"
    title = doc.title_en.rstrip(".")
    if m.get("volume"):
        issue = f"({m['issue']})" if m.get("issue") else ""
        pages = _pages(m, "–")
        return f"{authors} ({date}). {title}. {m.get('journal') or doc.source.name}, {m['volume']}{issue}" \
               f"{', ' + pages if pages else ''}. {_link(doc)}"
    return f"{authors} ({date}). {title}. {doc.source.name}. {_link(doc)}"


def chicago(doc: Document) -> str:
    m = doc.meta or {}
    authors = _chicago_names(doc.authors) if doc.authors else doc.source.name
    year = str(doc.published_at.year) if doc.published_at else "n.d."
    title = doc.title_en.rstrip(".")
    if m.get("volume"):
        issue = f" ({m['issue']})" if m.get("issue") else ""
        pages = _pages(m, "–")
        return f"{authors}. {year}. “{title}.” {m.get('journal') or doc.source.name} {m['volume']}{issue}" \
               f"{': ' + pages if pages else ''}. {_link(doc)}."
    when = f"{MONTHS[doc.published_at.month - 1]} {doc.published_at.day}, " if doc.published_at else ""
    return f"{authors}. {year}. “{title}.” {doc.source.name}, {when}{year}. {_link(doc)}."


def _bib_escape(text: str) -> str:
    return re.sub(r"([&%$#_{}])", r"\\\1", text)


def bibtex(doc: Document) -> str:
    m = doc.meta or {}
    first = _split(doc.authors[0])[1] if doc.authors else doc.source.name.split()[0]
    year = str(doc.published_at.year) if doc.published_at else "nd"
    word = next((w for w in re.findall(r"[A-Za-z]+", doc.title_en) if len(w) > 3), "item")
    key = re.sub(r"[^A-Za-z0-9]", "", f"{first}{year}{word}").lower()
    fields: list[tuple[str, str]] = []
    authors = " and ".join(f"{f}, {g}".strip(", ") for g, f in map(_split, doc.authors)) if doc.authors \
        else "{" + doc.source.name + "}"
    fields.append(("author", authors))
    fields.append(("title", "{" + doc.title_en + "}"))
    if m.get("volume") or doc.source.kind == "journal":
        kind = "article"
        fields.append(("journal", m.get("journal") or doc.source.name))
        for k, out in (("volume", "volume"), ("issue", "number")):
            if m.get(k):
                fields.append((out, m[k]))
        if _pages(m, "--"):
            fields.append(("pages", _pages(m, "--")))
    elif doc.source.kind in ("think_tank", "government"):
        kind = "techreport"
        fields.append(("institution", doc.source.name))
    else:
        kind = "misc"
        fields.append(("howpublished", doc.source.name))
    fields.append(("year", year))
    if m.get("doi"):
        fields.append(("doi", m["doi"]))
    fields.append(("url", doc.url))
    body = ",\n".join(f"  {k} = {{{_bib_escape(v) if k not in ('url', 'doi', 'title', 'author') else v}}}"
                      for k, v in fields)
    return f"@{kind}{{{key},\n{body}\n}}"


def translation_citation(doc: Document, site_name: str, site_url: str) -> str:
    tr = doc.translation
    year = tr.published_at.year if tr and tr.published_at else ""
    who = "، ".join(doc.authors) if doc.authors else doc.source.name
    return (f"{site_name} ({year}). {tr.title_ar} [ترجمة عربية لمادة: {doc.title_en}، تأليف {who}، "
            f"{doc.source.name}]. {site_url.rstrip('/')}/articles/{doc.id}")


def all_citations(doc: Document, site_name: str, site_url: str) -> dict:
    return {"apa": apa(doc), "chicago": chicago(doc), "bibtex": bibtex(doc),
            "translation": translation_citation(doc, site_name, site_url)}
