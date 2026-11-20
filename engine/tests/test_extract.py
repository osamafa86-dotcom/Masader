import pymupdf

from marsad.extract.html import extract_html, paragraphs_from_fragment
from marsad.extract.pdf import extract_pdf


def test_extract_html_article(fixture_bytes):
    ex = extract_html(fixture_bytes("article.html").decode(), "https://example-review.test/2026/11/gray-zone-deterrence")
    assert ex.title.startswith("Deterrence in the Gray Zone")
    assert len(ex.paragraphs) >= 7
    joined = ex.text
    assert "deterrence by denial can be adapted" in joined
    for noise in ("Subscribe to our newsletter", "Most read", "Privacy", "By Jane Analyst"):
        assert noise not in joined
    assert ex.authors == ["Jane Analyst"]
    assert ex.published_at is not None and ex.published_at.year == 2026


def test_fragment_paragraphs_keep_order():
    html = "<p>One.</p><ul><li><p>Two.</p></li></ul><blockquote>Three.</blockquote><p>By John Smith</p><p>Four.</p>"
    assert paragraphs_from_fragment(html) == ["One.", "Two.", "Three.", "Four."]


def _make_pdf() -> bytes:
    doc = pymupdf.open()
    body = [
        "Strategic competition in the Arctic has intensified since 2022. Melting ice opens new routes.",
        "Russia has reopened Soviet-era bases along its northern coast and expanded its icebreaker fleet.",
        "The alliance response remains fragmented, with members prioritising different threats and budgets.",
    ]
    for i, para in enumerate(body, start=1):
        page = doc.new_page()
        page.insert_text((72, 40), "PARAMETERS 56(4) Winter 2026", fontsize=8)
        page.insert_textbox(pymupdf.Rect(72, 100, 520, 300), para, fontsize=11)
        page.insert_text((300, 800), str(i), fontsize=8)
    doc.set_metadata({"title": "Arctic Competition and the Alliance", "author": "A. Author; B. Writer"})
    return doc.tobytes()


def test_extract_pdf_removes_running_headers_and_page_numbers():
    ex = extract_pdf(_make_pdf())
    assert ex.title == "Arctic Competition and the Alliance"
    assert ex.authors == ["A. Author", "B. Writer"]
    assert len(ex.paragraphs) == 3
    assert ex.paragraphs[0].startswith("Strategic competition in the Arctic")
    assert all("PARAMETERS" not in p for p in ex.paragraphs)
