import json
from importlib import resources

from fastapi.testclient import TestClient
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.glossary import Term, relevant_terms
from marsad.ai.llm import FakeLLM
from marsad.ai.tasks import qa_check
from marsad.api.app import create_app
from marsad.demo import load_demo
from marsad.lang import detect
from marsad.models import Document, GlossaryTerm, PublishLevel, RightsLevel, Stage
from marsad.pipeline import load_terms
from marsad.seed import seed_all
from marsad.worker import run_once
from marsad.fetch.http import PoliteClient
from tests.helpers import make_source, mock_transport

FR = next(a for a in json.loads(resources.files("marsad.data").joinpath("demo_articles.json").read_text())["articles"]
          if a.get("language") == "fr")


def test_detect():
    assert detect(" ".join(FR["paragraphs_en"])) == "fr"
    assert detect("Ядерное сдерживание остаётся основой стратегической стабильности.") == "ru"
    assert detect("הרתעה היא מרכיב מרכזי בתפיסת הביטחון הלאומי.") == "he"
    assert detect("中国的国际战略与地区安全形势") == "zh"
    assert detect("الردع النووي والاستقرار الاستراتيجي") == "ar"
    assert detect("Deterrence by denial remains the core of the argument in the paper.") == "en"
    assert detect("1234 5678") == "en"


def test_glossary_matching_per_script():
    terms = [Term("dissuasion", "الردع"), Term("OTAN", "الناتو"), Term("сдерживание", "الردع"),
             Term("中国", "الصين"), Term("הרתעה", "الردع")]
    assert {t.en for t in relevant_terms("La dissuasion face à l'OTAN", terms)} == {"dissuasion", "OTAN"}
    assert {t.en for t in relevant_terms("ядерное сдерживание России", terms)} == {"сдерживание"}
    assert {t.en for t in relevant_terms("中国的国际战略", terms)} == {"中国"}
    assert {t.en for t in relevant_terms("הרתעה ישראלית", terms)} == {"הרתעה"}


def test_french_reference_translation_passes_qa(db, settings):
    seed_all(db)
    db.commit()
    terms = load_terms(db, "fr")
    assert {"dissuasion", "OTAN"} <= {t.en for t in terms} and "deterrence" not in {t.en for t in terms}
    report, _ = qa_check(FR["paragraphs_en"], FR["paragraphs_ar"], terms, settings, lang="fr")
    assert report["issues"] == [], report
    left = list(FR["paragraphs_ar"])
    left[1] = FR["paragraphs_en"][1]  # untranslated French paragraph
    report, _ = qa_check(FR["paragraphs_en"], left, terms, settings, lang="fr")
    assert any(i["paragraph_id"] == 1 and i["severity"] == "high" for i in report["issues"])


def test_french_demo_published_with_language(db, session_factory, settings):
    seed_all(db)
    load_demo(db, settings)
    doc = db.scalar(select(Document).where(Document.title_en == FR["title_en"]))
    assert doc.language == "fr" and doc.stage == Stage.published
    assert doc.translation.paragraphs_ar == FR["paragraphs_ar"]
    proposed = db.scalar(select(GlossaryTerm).where(GlossaryTerm.term_en == "stricte suffisance"))
    assert proposed.lang == "fr" and proposed.status == "proposed"
    api = TestClient(create_app(settings=settings, factory=session_factory, llm=FakeLLM(demo_handler),
                                embedder=None, mailer=None))
    detail = api.get(f"/api/articles/{doc.id}").json()
    assert detail["source_language"] == "fr" and detail["publish_level"] == "full"
    assert {"OTAN", "dissuasion"} <= {g["en"] for g in detail["glossary"]}


def test_arabic_source_is_summarised_not_translated(db, session_factory, settings):
    seed_all(db)
    src = make_source(db, slug="arabic-center", rights=RightsLevel.a)
    src.language = "ar"
    db.commit()
    body = "".join(f"<p>الفقرة {i}: يناقش المركز مستقبل الردع في المنطقة الرمادية وأثره على أمن الممرات البحرية في المنطقة.</p>"
                   for i in range(8))
    feed = ('<?xml version="1.0"?><rss version="2.0"><channel><title>t</title><item><title>دراسة عربية</title>'
            '<link>https://ar.test/a</link><description>ملخص</description></item></channel></rss>')
    http = PoliteClient(settings, transport=mock_transport({
        "https://example-review.test/feed/": (200, feed),
        "https://ar.test/a": (200, f"<html><body><article><h1>دراسة عربية</h1>{body}</article></body></html>",
                              {"content-type": "text/html"})}))
    llm = FakeLLM(demo_handler)
    for _ in range(6):
        run_once(session_factory, llm, http, settings)
    db.expire_all()
    doc = db.scalar(select(Document).where(Document.title_en == "دراسة عربية"))
    assert doc.language == "ar" and doc.stage == Stage.review and doc.max_level == PublishLevel.full
    assert doc.translation.paragraphs_ar == doc.paragraphs_en
    assert doc.translation.qa_report["original_arabic"] is True
    assert not [p for t, p in llm.calls if t == "translate"]
