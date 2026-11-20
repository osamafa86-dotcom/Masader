import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.api.app import create_app
from marsad.api.auth import hash_password
from marsad.extract.html import find_pdf_link
from marsad.extract.pdf import extract_pdf
from marsad.fetch.http import PoliteClient
from marsad.models import Document, RightsLevel, Stage, User
from marsad.seed import seed_taxonomy
from marsad.worker import run_once
from tests.helpers import make_source, mock_transport

L1 = "Left column first paragraph explains the origins of the doctrine and its early reception."
L2 = "left column continues after a column break and ends the argument about doctrine."
L3 = "Left column second paragraph turns to procurement and the industrial base."
R1 = "Right column first paragraph examines the operational record in two campaigns."
R2 = "Right column second paragraph concludes with recommendations for planners."
FOOT = "1 See the archival record in Box 12, Folder 3, for the original memorandum."


def two_column_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_textbox(pymupdf.Rect(50, 40, 550, 80), "A Study of Doctrine and Its Consequences", fontsize=16)
    # Insert right column first, at the same heights as the left, so naive y-sorting would interleave them.
    page.insert_textbox(pymupdf.Rect(320, 100, 550, 200), R1, fontsize=10)
    page.insert_textbox(pymupdf.Rect(320, 220, 550, 320), R2, fontsize=10)
    page.insert_textbox(pymupdf.Rect(50, 100, 280, 200), L1, fontsize=10)
    page.insert_textbox(pymupdf.Rect(50, 220, 280, 320), L3, fontsize=10)
    page.insert_textbox(pymupdf.Rect(50, 720, 550, 760), FOOT, fontsize=7)
    return doc.tobytes()


def test_two_column_reading_order_and_footnotes_removed():
    ex = extract_pdf(two_column_pdf())
    assert ex.title == "A Study of Doctrine and Its Consequences"
    assert ex.paragraphs == [L1, L3, R1, R2]


def test_column_continuation_is_merged():
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_textbox(pymupdf.Rect(50, 100, 280, 200), "Opening paragraph that ends without a full stop and", fontsize=10)
    page.insert_textbox(pymupdf.Rect(320, 100, 550, 200), L2, fontsize=10)
    doc.set_metadata({"title": "T"})
    ex = extract_pdf(doc.tobytes())
    assert ex.paragraphs == ["Opening paragraph that ends without a full stop and " + L2]


def test_find_pdf_link():
    landing = '<html><head><meta name="citation_pdf_url" content="/pubs/RR123.pdf"></head></html>'
    assert find_pdf_link(landing, "https://think.test/pubs/RR123.html") == "https://think.test/pubs/RR123.pdf"
    links = '<a href="/x.pdf">Brochure</a><a href="https://other.test/y.pdf">Download PDF</a><a href="/full.pdf">Download PDF</a>'
    assert find_pdf_link(links, "https://think.test/r.html") == "https://think.test/full.pdf"
    assert find_pdf_link("<a href='/a.html'>PDF</a>", "https://think.test/r.html") is None


def _long_pdf() -> bytes:
    doc = pymupdf.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 520, 700),
                            f"Chapter {i + 1}. " + " ".join(f"Finding number {j} of the report on force posture." for j in range(15)),
                            fontsize=10)
    return doc.tobytes()


@pytest.fixture
def setup(db, session_factory, settings):
    seed_taxonomy(db)
    make_source(db, slug="thinktank", rights=RightsLevel.c, feed_url=None)
    db.add(User(email="ed@example.org", name="محرر", password_hash=hash_password("secret-pass")))
    db.commit()
    landing = ('<html><head><title>Force Posture Report</title></head><body><article><h1>Force Posture Report</h1>'
               '<p>This report examines force posture in Europe and recommends changes to basing and readiness.</p>'
               '<p><a href="/pubs/RR1.pdf">Download PDF</a></p></article></body></html>')
    routes = {
        "https://think.test/pubs/RR1.html": (200, landing, {"content-type": "text/html"}),
        "https://think.test/pubs/RR1.pdf": (200, _long_pdf(), {"content-type": "application/pdf"}),
    }
    http = PoliteClient(settings, transport=mock_transport(routes))
    llm = FakeLLM(demo_handler)
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=llm))
    token = api.post("/api/editor/login", json={"email": "ed@example.org", "password": "secret-pass"}).json()["token"]
    return api, {"Authorization": f"Bearer {token}"}, http, llm


def test_import_follows_report_pdf(db, session_factory, settings, setup):
    api, h, http, llm = setup
    r = api.post("/api/editor/import", headers=h, json={"url": "https://think.test/pubs/RR1.html", "source_slug": "thinktank"})
    assert r.status_code == 201
    doc_id = r.json()["id"]
    assert api.post("/api/editor/import", headers=h,
                    json={"url": "https://think.test/pubs/RR1.html?utm_source=x", "source_slug": "thinktank"}).status_code == 409
    for _ in range(5):
        run_once(session_factory, llm, http, settings)
    db.expire_all()
    doc = db.get(Document, doc_id)
    assert doc.stage == Stage.review, doc.error
    assert doc.title_en == "Force Posture Report"
    assert doc.word_count > 300 and doc.paragraphs_en[0].startswith("Chapter 1.")
    assert "recommends changes to basing" in doc.abstract_en


@pytest.mark.parametrize("url", ["http://localhost:8000/api/health", "http://127.0.0.1/x", "http://10.0.0.5/x",
                                 "file:///etc/passwd", "http://169.254.169.254/latest/meta-data", "http://db.internal/x"])
def test_import_rejects_internal_urls(setup, url):
    api, h, _, _ = setup
    assert api.post("/api/editor/import", headers=h, json={"url": url, "source_slug": "thinktank"}).status_code == 400
