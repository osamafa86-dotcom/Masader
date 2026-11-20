from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.authors import split_names
from marsad.citations import apa, bibtex, chicago
from marsad.demo import load_demo
from marsad.models import Author, Document, Source
from marsad.seed import seed_all


def test_split_names():
    assert split_names(["Jane Doe and John Roe"]) == ["Jane Doe", "John Roe"]
    assert split_names(["Doe, Jane"]) == ["Doe, Jane"]
    assert split_names(["Ann Lee, Bo Kim, and Cy Park"]) == ["Ann Lee", "Bo Kim", "Cy Park"]
    assert split_names(["By Dr. Jane Doe", "Jane Doe"]) == ["Jane Doe"]
    assert split_names(["Lt. Col. Sam Hill"]) == ["Sam Hill"]


def _journal_doc() -> Document:
    src = Source(slug="ins", name="Intelligence and National Security", kind="journal")
    return Document(title_en="Coalition Intelligence Sharing and the Limits of Trust",
                    authors=["Maria Lopez", "Tom J. Reed"], url="https://journal.test/doi/full/x",
                    published_at=datetime(2026, 11, 16, tzinfo=timezone.utc), source=src,
                    meta={"journal": "Intelligence and National Security", "volume": "41", "issue": "6",
                          "start_page": "812", "end_page": "835", "doi": "10.1080/02684527.2026.2401234"})


def _report_doc() -> Document:
    src = Source(slug="rand", name="RAND Corporation", kind="think_tank")
    return Document(title_en="Force Posture in Europe", authors=[], url="https://think.test/RR1.html",
                    published_at=datetime(2026, 3, 5, tzinfo=timezone.utc), source=src, meta={})


def test_journal_citations():
    d = _journal_doc()
    assert apa(d) == ("Lopez, M., & Reed, T. J. (2026). Coalition Intelligence Sharing and the Limits of Trust. "
                      "Intelligence and National Security, 41(6), 812–835. https://doi.org/10.1080/02684527.2026.2401234")
    assert chicago(d) == ("Lopez, Maria, and Tom J. Reed. 2026. “Coalition Intelligence Sharing and the Limits of Trust.” "
                          "Intelligence and National Security 41 (6): 812–835. https://doi.org/10.1080/02684527.2026.2401234.")
    bib = bibtex(d)
    assert bib.startswith("@article{lopez2026coalition,")
    assert "author = {Lopez, Maria and Reed, Tom J.}" in bib and "pages = {812--835}" in bib and "number = {6}" in bib


def test_report_without_authors_uses_institution():
    d = _report_doc()
    assert apa(d) == "RAND Corporation (2026, March 5). Force Posture in Europe. RAND Corporation. https://think.test/RR1.html"
    assert bibtex(d).startswith("@techreport{rand2026force,")
    assert "institution = {RAND Corporation}" in bibtex(d)


def test_author_pages_and_citations_in_api(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    assert db.scalar(select(Author).where(Author.slug == "jane-analyst")) is not None
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler)))
    author = api.get("/api/authors/jane-analyst").json()
    assert author["name"] == "Jane Analyst" and author["total"] == 1
    assert api.get("/api/authors/nobody").status_code == 404
    arctic = db.scalar(select(Document).where(Document.title_en == "Arctic Competition and the Alliance"))
    detail = api.get(f"/api/articles/{arctic.id}").json()
    assert [a["slug"] for a in detail["authors_detail"]] == ["a-author", "b-writer"]
    assert set(detail["citations"]) == {"apa", "chicago", "bibtex", "translation"}
    assert "ترجمة عربية لمادة" in detail["citations"]["translation"]
