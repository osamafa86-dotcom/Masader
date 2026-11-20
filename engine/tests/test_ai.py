import json
from importlib import resources

import pytest

from marsad.ai.demo import demo_handler
from marsad.ai.glossary import Term, relevant_terms
from marsad.ai.llm import AnthropicLLM, FakeLLM, LLMRefusal
from marsad.ai.tasks import (
    DocInput,
    TranslationIncomplete,
    chunk_ids,
    classify,
    limit_quotes,
    qa_check,
    summarize,
    translate,
)
from marsad.extract.html import extract_html

DEMO = json.loads(resources.files("marsad.data").joinpath("demo_articles.json").read_text(encoding="utf-8"))["articles"][0]
TERMS = [
    Term("deterrence", "الردع"),
    Term("deterrence by denial", "الردع بالمنع", ("الردع بالحرمان",)),
    Term("deterrence by punishment", "الردع بالعقاب"),
    Term("gray zone", "المنطقة الرمادية"),
    Term("coercion", "الإكراه", ("القسر",)),
    Term("escalation", "التصعيد"),
    Term("escalation ladder", "سلّم التصعيد"),
    Term("A2/AD", "منع الوصول/حرمان المنطقة"),
    Term("NATO", "حلف شمال الأطلسي (الناتو)", ("الناتو",)),
]


@pytest.fixture
def article(fixture_bytes):
    ex = extract_html(fixture_bytes("article.html").decode(), "https://example-review.test/x")
    return DocInput(title=ex.title or DEMO["title_en"], paragraphs=ex.paragraphs, source_name="Example Review")


def test_relevant_terms_matching():
    found = relevant_terms("NATO allies debate deterrence by denial; nato is lowercase here.", TERMS)
    assert [t.en for t in found] == ["deterrence by denial", "deterrence", "NATO"]
    assert relevant_terms("The deterrent effect", TERMS) == []  # whole words only


def test_reference_translation_passes_qa(article, settings):
    report, _ = qa_check(article.paragraphs, DEMO["paragraphs_ar"], TERMS, settings)
    assert report["issues"] == [], report
    assert report["score"] == 100


def test_qa_flags_numbers_terms_and_missing(article, settings):
    ar = list(DEMO["paragraphs_ar"])
    ar[1] = ar[1].replace("2024", "الماضي")           # drop a number
    ar[2] = ar[2].replace("الردع بالعقاب", "الزجر")     # glossary violation
    ar[4] = ""                                         # missing paragraph
    report, _ = qa_check(article.paragraphs, ar, TERMS, settings)
    kinds = {(i["paragraph_id"], i["kind"], i["severity"]) for i in report["issues"]}
    assert (1, "number", "medium") in kinds
    assert (2, "terminology", "medium") in kinds
    assert (4, "omission", "high") in kinds
    assert report["high"] == 1 and report["score"] < 100


def test_qa_accepts_arabic_indic_digits_and_variants(settings):
    en = ["NATO members spent 2.1 percent in 2024 on coercion research."]
    ar = ["أنفق أعضاء الناتو ٢٫١ في المئة في عام ٢٠٢٤ على أبحاث القسر."]
    report, _ = qa_check(en, ar, TERMS, settings)
    assert report["issues"] == []


def test_classify_filters_and_clamps(article, settings):
    llm = FakeLLM(lambda task, p: {"topics": ["deterrence", "not-a-topic"], "regions": ["mars"],
                                   "doc_type": "blog", "importance": 9, "keywords_en": ["a"]})
    data, res = classify(llm, article, settings)
    assert data == {"topics": ["deterrence"], "regions": [], "doc_type": "commentary", "importance": 5,
                    "keywords_en": ["a"]}
    assert res.cost_usd > 0


def test_summary_quotes_limited_to_150_words(article, settings):
    long_quote = {"en": " ".join(["word"] * 120), "ar": "اقتباس"}
    short = {"en": "short quote here", "ar": "قصير"}
    assert limit_quotes([long_quote, long_quote, short, short], 150) == [long_quote, short]
    assert len(limit_quotes([short] * 5, 150)) == 3

    llm = FakeLLM(lambda task, p: {**DEMO["summary"], "quotes": [long_quote, long_quote]})
    data, _ = summarize(llm, article, TERMS, settings)
    assert sum(len(q["en"].split()) for q in data["quotes"]) <= 150
    sent = llm.calls[0][1]
    assert {"en": "gray zone", "ar": "المنطقة الرمادية"} in sent["glossary"]


def test_translate_retries_only_missing_paragraphs(article, settings):
    calls = []

    def handler(task, payload):
        ids = [p["id"] for p in payload["paragraphs"]]
        calls.append(ids)
        if len(calls) == 1:  # first call: drop paragraph 2 and return an empty paragraph 3
            return {"paragraphs": [{"id": i, "ar": "" if i == 3 else DEMO["paragraphs_ar"][i]} for i in ids if i != 2],
                    "notes": [{"id": 0, "note_ar": "ملاحظة"}]}
        return {"paragraphs": [{"id": i, "ar": DEMO["paragraphs_ar"][i]} for i in ids], "notes": []}

    llm = FakeLLM(handler)
    settings.chunk_words = 10_000
    result = translate(llm, article, TERMS, settings)
    assert result.paragraphs == DEMO["paragraphs_ar"]
    assert [p["id"] for p in llm.calls[1][1]["paragraphs"]] == [2, 3]
    assert result.notes == [{"id": 0, "note_ar": "ملاحظة"}]
    assert len(result.calls) == 2 and result.cost_usd > 0


def test_translate_raises_when_paragraph_still_missing(article, settings):
    llm = FakeLLM(lambda task, p: {"paragraphs": [{"id": x["id"], "ar": "نص"} for x in p["paragraphs"] if x["id"] != 5],
                                   "notes": []})
    with pytest.raises(TranslationIncomplete) as exc:
        translate(llm, article, TERMS, settings)
    assert exc.value.missing == [5]


def test_long_document_is_chunked_in_order(settings):
    paragraphs = [f"Paragraph {i} " + "word " * 300 for i in range(20)]  # 20 x ~302 words
    assert len(chunk_ids(paragraphs, 1800)) == 4
    llm = FakeLLM(lambda task, p: {"paragraphs": [{"id": x["id"], "ar": f"فقرة {x['id']}"} for x in p["paragraphs"]],
                                   "notes": []})
    result = translate(llm, DocInput(title="Long", paragraphs=paragraphs), [], settings)
    assert len(llm.calls) == 4
    assert result.paragraphs == [f"فقرة {i}" for i in range(20)]


def test_demo_handler_reproduces_reference(article, settings):
    llm = FakeLLM(demo_handler)
    result = translate(llm, article, TERMS, settings)
    assert result.paragraphs == DEMO["paragraphs_ar"]


class _Block:
    def __init__(self, type, text=None):
        self.type, self.text = type, text


class _Msg:
    def __init__(self, stop_reason, text='{"ok": true}'):
        self.stop_reason = stop_reason
        self.stop_details = type("D", (), {"category": "cyber"})() if stop_reason == "refusal" else None
        self.content = [_Block("thinking"), _Block("text", text)]
        self.model = "claude-opus-5-5"
        self.usage = type("U", (), {"input_tokens": 1000, "output_tokens": 500,
                                    "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0})()


class _Stream:
    def __init__(self, msg, sink):
        self.msg, self.sink = msg, sink

    def __call__(self, **kwargs):
        self.sink.append(kwargs)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


def _client(msg, sink):
    beta = type("B", (), {})()
    beta.messages = type("M", (), {})()
    beta.messages.stream = _Stream(msg, sink)
    client = type("C", (), {})()
    client.beta = beta
    return client


def test_anthropic_llm_request_shape_and_parsing():
    sink: list[dict] = []
    llm = AnthropicLLM(client=_client(_Msg("end_turn"), sink))
    res = llm.json(task="t", model="claude-opus-5-5", system="SYS", user="{}", schema={"type": "object"}, effort="medium")
    assert res.data == {"ok": True}
    assert res.cost_usd == pytest.approx((1000 * 4 + 500 * 20) / 1e6)
    kw = sink[0]
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}, "effort": "medium"}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}

    sink.clear()
    AnthropicLLM(client=_client(_Msg("end_turn"), sink)).json(task="t", model="claude-haiku-5-5", system="S",
                                                              user="{}", schema={})
    assert "fallbacks" not in sink[0]  # Haiku has no server-side fallback


def test_anthropic_llm_refusal_raises():
    llm = AnthropicLLM(client=_client(_Msg("refusal"), []))
    with pytest.raises(LLMRefusal):
        llm.json(task="t", model="claude-opus-5-5", system="S", user="{}", schema={})
