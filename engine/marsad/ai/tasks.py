"""The four AI tasks: classify, summarize, translate (chunked) and QA."""

import json
import re
from dataclasses import dataclass, field

from marsad.ai import prompts, schemas
from marsad.ai.glossary import Term, as_prompt, relevant_terms
from marsad.ai.llm import LLM, LLMResult
from marsad.arabic import loose_form, normalize_ar
from marsad.config import Settings
from marsad.lang import script_of


@dataclass
class DocInput:
    title: str
    paragraphs: list[str]
    source_name: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    language: str = "en"


class TranslationIncomplete(Exception):
    def __init__(self, missing: list[int]):
        super().__init__(f"model did not return paragraphs {missing}")
        self.missing = missing


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _words(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------- classify
def classify(llm: LLM, doc: DocInput, settings: Settings) -> tuple[dict, LLMResult]:
    opening, count = [], 0
    for p in doc.paragraphs:
        opening.append(p)
        count += _words(p)
        if count > 1500:
            break
    payload = {"title": doc.title, "source": doc.source_name, "abstract": doc.abstract or "", "source_language": doc.language,
               "opening_text": "\n\n".join(opening), "total_words": sum(_words(p) for p in doc.paragraphs)}
    res = llm.json(task="classify", model=settings.model_classify, system=prompts.CLASSIFY, user=_dump(payload),
                   schema=schemas.CLASSIFICATION, max_tokens=2000, effort=settings.effort_classify)
    d = res.data
    data = {
        "topics": [t for t in d.get("topics", []) if t in schemas.TOPICS][:3],
        "regions": [r for r in d.get("regions", []) if r in schemas.REGIONS][:3],
        "doc_type": d.get("doc_type") if d.get("doc_type") in schemas.DOC_TYPES else "commentary",
        "importance": min(5, max(1, int(d.get("importance", 3)))),
        "keywords_en": [k for k in d.get("keywords_en", []) if isinstance(k, str)][:8],
    }
    return data, res


# ---------------------------------------------------------------- summarize
MAX_SUMMARY_INPUT_WORDS = 30000


def limit_quotes(quotes: list[dict], max_words: int) -> list[dict]:
    kept, total = [], 0
    for q in quotes[:3]:
        n = _words(q.get("en", ""))
        if not n or total + n > max_words:
            continue
        kept.append({"en": q["en"].strip(), "ar": q.get("ar", "").strip()})
        total += n
    return kept


def summarize(llm: LLM, doc: DocInput, terms: list[Term], settings: Settings) -> tuple[dict, LLMResult]:
    paragraphs, count = [], 0
    for p in doc.paragraphs:
        if count + _words(p) > MAX_SUMMARY_INPUT_WORDS:
            break
        paragraphs.append(p)
        count += _words(p)
    text = "\n\n".join(paragraphs)
    payload = {"title": doc.title, "source": doc.source_name, "authors": doc.authors, "abstract": doc.abstract or "",
               "text": text, "truncated": len(paragraphs) < len(doc.paragraphs), "abstract_only": not doc.paragraphs,
               "source_language": doc.language,
               "glossary": as_prompt(relevant_terms(f"{doc.title}\n{doc.abstract or ''}\n{text}", terms))}
    res = llm.json(task="summarize", model=settings.model_summarize, system=prompts.SUMMARIZE, user=_dump(payload),
                   schema=schemas.SUMMARY, max_tokens=8000, effort=settings.effort_translate)
    d = dict(res.data)
    d["key_points_ar"] = [p for p in d.get("key_points_ar", []) if p.strip()][:7]
    d["recommendations_ar"] = [p for p in d.get("recommendations_ar", []) if p.strip()][:7]
    d["quotes"] = limit_quotes(d.get("quotes", []), settings.max_quote_words)
    if not doc.paragraphs:  # abstract-only: at most one quote, and it must come from the abstract itself
        abstract = (doc.abstract or "").lower()
        d["quotes"] = [q for q in d["quotes"] if q["en"].lower().strip(" .\"'“”") in abstract][:1]
        d["abstract_only"] = True
    d["new_terms"] = [t for t in d.get("new_terms", []) if t.get("en") and t.get("ar")][:15]
    return d, res


# ---------------------------------------------------------------- translate
@dataclass
class TranslationResult:
    paragraphs: list[str]
    notes: list[dict]
    calls: list[LLMResult]

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)


def chunk_ids(paragraphs: list[str], max_words: int) -> list[list[int]]:
    chunks: list[list[int]] = [[]]
    count = 0
    for i, p in enumerate(paragraphs):
        n = _words(p)
        if chunks[-1] and count + n > max_words:
            chunks.append([])
            count = 0
        chunks[-1].append(i)
        count += n
    return [c for c in chunks if c]


def _translate_ids(llm: LLM, doc: DocInput, ids: list[int], terms: list[Term], context_ar: str,
                   settings: Settings) -> tuple[dict[int, str], list[dict], LLMResult]:
    chunk_text = "\n".join(doc.paragraphs[i] for i in ids)
    payload = {"title": doc.title, "context_summary_ar": context_ar, "source_language": doc.language,
               "glossary": as_prompt(relevant_terms(f"{doc.title}\n{chunk_text}", terms)),
               "paragraphs": [{"id": i, "en": doc.paragraphs[i]} for i in ids]}
    words = sum(_words(doc.paragraphs[i]) for i in ids)
    res = llm.json(task="translate", model=settings.model_translate, system=prompts.TRANSLATE, user=_dump(payload),
                   schema=schemas.TRANSLATION, max_tokens=min(64000, 4000 + words * 6),
                   effort=settings.effort_translate)
    wanted = set(ids)
    got = {p["id"]: p["ar"].strip() for p in res.data.get("paragraphs", [])
           if p.get("id") in wanted and p.get("ar", "").strip()}
    notes = [n for n in res.data.get("notes", []) if n.get("id") in wanted and n.get("note_ar")]
    return got, notes, res


def translate_one(llm: LLM, doc: DocInput, index: int, terms: list[Term], settings: Settings,
                  context_ar: str = "") -> tuple[str, list[dict], LLMResult]:
    """Translate a single paragraph, keeping its real id so the model sees its position."""
    got, notes, res = _translate_ids(llm, doc, [index], terms, context_ar, settings)
    if index not in got:
        raise TranslationIncomplete([index])
    return got[index], notes, res


def translate(llm: LLM, doc: DocInput, terms: list[Term], settings: Settings, context_ar: str = "") -> TranslationResult:
    out: dict[int, str] = {}
    notes: list[dict] = []
    calls: list[LLMResult] = []
    for ids in chunk_ids(doc.paragraphs, settings.chunk_words):
        got, n, res = _translate_ids(llm, doc, ids, terms, context_ar, settings)
        calls.append(res)
        notes += n
        missing = [i for i in ids if i not in got]
        if missing:  # one retry, only for the paragraphs that came back missing or empty
            retry, n2, res2 = _translate_ids(llm, doc, missing, terms, context_ar, settings)
            calls.append(res2)
            notes += n2
            got.update(retry)
            still = [i for i in missing if i not in got]
            if still:
                raise TranslationIncomplete(still)
        out.update(got)
    return TranslationResult(paragraphs=[out[i] for i in range(len(doc.paragraphs))], notes=notes, calls=calls)


# ---------------------------------------------------------------- QA
NUMBER = re.compile(r"(?<![A-Za-z\d])\d[\d,.]*\d(?![A-Za-z])|(?<![A-Za-z\d])\d(?![A-Za-z\d])")
LATIN = re.compile(r"[A-Za-z]")
ARABIC = re.compile(r"[؀-ۿ]")
SEVERITY_WEIGHT = {"high": 15, "medium": 5, "low": 1}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUMBER.findall(text)}


def _has_term(ar_text: str, term: Term) -> bool:
    haystack = loose_form(ar_text)
    return any(loose_form(form) in haystack for form in (term.ar, *term.variants) if form)


def deterministic_issues(en: list[str], ar: list[str | None], terms: list[Term], lang: str = "en") -> list[dict]:
    issues: list[dict] = []
    source_script = script_of(lang)
    if len(en) != len(ar):
        issues.append({"paragraph_id": -1, "kind": "omission", "severity": "high",
                       "detail_ar": f"عدد الفقرات المترجمة ({len(ar)}) لا يطابق الأصل ({len(en)})."})
    for i, src in enumerate(en):
        tgt = ar[i] if i < len(ar) else None
        if not tgt or not tgt.strip():
            issues.append({"paragraph_id": i, "kind": "omission", "severity": "high", "detail_ar": "الفقرة غير مترجمة."})
            continue
        leftover = len(source_script.findall(tgt))
        letters = leftover + len(ARABIC.findall(tgt))
        if letters and leftover / letters > 0.4:
            issues.append({"paragraph_id": i, "kind": "omission", "severity": "high",
                           "detail_ar": "نسبة كبيرة من الفقرة بقيت بلغة الأصل."})
        missing_numbers = _numbers(src) - _numbers(normalize_ar(tgt))
        if missing_numbers:
            issues.append({"paragraph_id": i, "kind": "number", "severity": "medium",
                           "detail_ar": "أرقام في الأصل غير موجودة في الترجمة: " + "، ".join(sorted(missing_numbers))})
        for term in relevant_terms(src, terms):
            if not _has_term(tgt, term):
                issues.append({"paragraph_id": i, "kind": "terminology", "severity": "medium",
                               "detail_ar": f"المصطلح «{term.en}» لم يُترجم بالصيغة المعتمدة «{term.ar}»."})
        if len(src.split()) >= 25 and lang != "zh":  # character ratios are meaningless for Chinese
            ratio = len(tgt) / max(1, len(src))
            if ratio < 0.45 or ratio > 1.8:
                issues.append({"paragraph_id": i, "kind": "omission" if ratio < 0.45 else "addition",
                               "severity": "medium", "detail_ar": f"طول الترجمة غير متناسب مع الأصل (نسبة {ratio:.2f})."})
    return issues


def _dedupe_terms(issues: list[dict]) -> list[dict]:
    """Drop exact duplicate issues (the same term can match twice through plural forms)."""
    seen, out = set(), []
    for it in issues:
        key = (it["paragraph_id"], it["kind"], it["detail_ar"])
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def qa_check(en: list[str], ar: list[str | None], terms: list[Term], settings: Settings,
             llm: LLM | None = None, lang: str = "en") -> tuple[dict, LLMResult | None]:
    issues = _dedupe_terms(deterministic_issues(en, ar, terms, lang))
    judge_res = None
    if llm is not None and settings.qa_llm_judge:
        payload = {"glossary": as_prompt(relevant_terms("\n".join(en), terms)),
                   "paragraphs": [{"id": i, "en": e, "ar": ar[i] if i < len(ar) else ""} for i, e in enumerate(en)]}
        judge_res = llm.json(task="qa_judge", model=settings.model_judge, system=prompts.JUDGE, user=_dump(payload),
                             schema=schemas.JUDGE, max_tokens=8000, effort="medium")
        for it in judge_res.data.get("issues", []):
            issues.append({**it, "by": "judge"})
    score = max(0, 100 - sum(SEVERITY_WEIGHT.get(i["severity"], 1) for i in issues))
    report = {"score": score, "issues": issues, "judge": judge_res is not None,
              "high": sum(1 for i in issues if i["severity"] == "high")}
    return report, judge_res
