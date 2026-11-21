import pytest
from sqlalchemy import select

from marsad.ai.demo import demo_handler
from marsad.ai.llm import FakeLLM
from marsad.demo import load_demo
from marsad.eval.golden import add_from_document, compare, load_golden, run_eval
from marsad.eval.metrics import chrf
from marsad.models import Document, User
from marsad.pipeline import publish
from marsad.seed import seed_all


def test_chrf():
    ref = "يقوم الردع النووي الفرنسي على عقيدة الكفاية الصارمة."
    assert chrf(ref, ref) == 100.0
    assert chrf("يَقُومُ الرَّدْعُ النووي الفرنسي على عقيدة الكفاية الصارمة.", ref) == 100.0  # diacritics ignored
    partial = chrf("يقوم الردع النووي على عقيدة.", ref)
    assert 30 < partial < 100
    assert chrf("نص مختلف تماماً عن المرجع", ref) < partial
    assert chrf("", ref) == 0.0


def test_golden_set_loads():
    items = load_golden()
    assert {i.language for i in items} >= {"en", "fr"}
    assert all(len(i.paragraphs_src) == len(i.reference_ar) for i in items)


@pytest.fixture
def seeded(db):
    seed_all(db)
    db.commit()
    return db


def test_eval_scores_reference_and_placeholder(seeded, settings):
    items = load_golden()
    good = run_eval(seeded, FakeLLM(demo_handler), settings, items, label="reference")
    assert good["summary"]["chrf_mean"] == 100.0 and good["summary"]["high_issues"] == 0
    assert good["summary"]["complete"] == len(items)

    def bad(task, payload):
        return {"paragraphs": [{"id": p["id"], "ar": "ترجمة ضعيفة لا علاقة لها بالأصل."} for p in payload["paragraphs"]],
                "notes": []}

    weak = run_eval(seeded, FakeLLM(bad), settings, items, label="weak")
    assert weak["summary"]["chrf_mean"] < 30 and weak["summary"]["number_issues"] > 0
    rows = {k: d for k, _, _, d in compare(good, weak)}
    assert rows["chrf_mean"] < -70

    def drops(task, payload):
        return {"paragraphs": [], "notes": []}

    incomplete = run_eval(seeded, FakeLLM(drops), settings, items[:1])
    assert incomplete["summary"]["complete"] == 0 and incomplete["results"][0]["missing"]


def test_add_reviewed_translation_to_golden_set(seeded, settings, tmp_path):
    load_demo(seeded, settings)
    gray = seeded.scalar(select(Document).where(Document.title_en.like("Deterrence in the Gray Zone%")))
    with pytest.raises(ValueError):
        add_from_document(gray, str(tmp_path))  # machine-only, not reviewed
    editor = User(email="e@example.org", name="e", password_hash="x")
    seeded.add(editor)
    seeded.flush()
    publish(seeded, gray, editor)
    seeded.commit()
    path = add_from_document(gray, str(tmp_path))
    items = load_golden(str(tmp_path))
    assert any(i.id == f"doc-{gray.id}" for i in items) and path.exists()
