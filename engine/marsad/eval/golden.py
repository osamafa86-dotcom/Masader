"""Golden set: files in marsad/data/golden (shipped) plus MARSAD_GOLDEN_DIR (grown by editors)."""

import json
import statistics
import time
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from sqlalchemy.orm import Session

from marsad.ai.llm import LLM
from marsad.ai.prompts import PROMPT_VERSION
from marsad.ai.tasks import DocInput, TranslationIncomplete, qa_check, translate
from marsad.config import Settings
from marsad.eval.metrics import chrf
from marsad.models import Document, PublishLevel
from marsad.pipeline import load_terms


@dataclass
class GoldenItem:
    id: str
    language: str
    title: str
    paragraphs_src: list[str]
    reference_ar: list[str]


def load_golden(extra_dir: str | None = None) -> list[GoldenItem]:
    files = [f for f in resources.files("marsad.data").joinpath("golden").iterdir() if f.name.endswith(".json")]
    if extra_dir and Path(extra_dir).is_dir():
        files += sorted(Path(extra_dir).glob("*.json"))
    items: dict[str, GoldenItem] = {}
    for f in sorted(files, key=lambda f: f.name):
        d = json.loads(f.read_text(encoding="utf-8"))
        if len(d["paragraphs_src"]) != len(d["reference_ar"]):
            raise ValueError(f"{f.name}: source and reference paragraph counts differ")
        items[d["id"]] = GoldenItem(d["id"], d.get("language", "en"), d["title"], d["paragraphs_src"], d["reference_ar"])
    return list(items.values())


def add_from_document(doc: Document, out_dir: str) -> Path:
    """Snapshot an editor-reviewed, fully translated document as a new reference."""
    tr = doc.translation
    if tr is None or not tr.human_reviewed or tr.publish_level != PublishLevel.full or not tr.paragraphs_ar:
        raise ValueError("only human-reviewed, fully translated items can join the golden set")
    item = {"id": f"doc-{doc.id}", "language": doc.language or "en", "title": doc.title_en, "source": doc.source.slug,
            "paragraphs_src": list(doc.paragraphs_en), "reference_ar": list(tr.paragraphs_ar),
            "origin": f"published item {doc.id}, reviewed {tr.reviewed_at.isoformat() if tr.reviewed_at else ''}"}
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    target = path / f"doc-{doc.id}.json"
    target.write_text(json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")
    return target


def run_eval(session: Session, llm: LLM, settings: Settings, items: list[GoldenItem], judge: bool = False,
             label: str = "") -> dict:
    results = []
    for it in items:
        terms = load_terms(session, it.language)
        doc = DocInput(title=it.title, paragraphs=it.paragraphs_src, language=it.language)
        started = time.monotonic()
        row: dict = {"id": it.id, "language": it.language, "paragraphs": len(it.paragraphs_src)}
        try:
            result = translate(llm, doc, terms, settings)
        except TranslationIncomplete as exc:
            results.append({**row, "complete": False, "missing": exc.missing, "chrf": 0.0, "cost_usd": 0.0})
            continue
        s = settings.model_copy(update={"qa_llm_judge": judge})
        report, judge_res = qa_check(it.paragraphs_src, result.paragraphs, terms, s, llm if judge else None, lang=it.language)
        scores = [chrf(h, r) for h, r in zip(result.paragraphs, it.reference_ar)]
        results.append({**row, "complete": True, "chrf": round(statistics.mean(scores), 2), "chrf_min": min(scores),
                         "qa_score": report["score"],
                         "issues": {sev: sum(1 for i in report["issues"] if i["severity"] == sev) for sev in ("high", "medium", "low")},
                         "terminology_issues": sum(1 for i in report["issues"] if i["kind"] == "terminology"),
                         "number_issues": sum(1 for i in report["issues"] if i["kind"] == "number"),
                         "cost_usd": round(result.cost_usd + (judge_res.cost_usd if judge_res else 0), 4),
                         "seconds": round(time.monotonic() - started, 1)})
    done = [r for r in results if r["complete"]]
    summary = {
        "items": len(results), "complete": len(done),
        "chrf_mean": round(statistics.mean(r["chrf"] for r in done), 2) if done else 0.0,
        "qa_score_mean": round(statistics.mean(r["qa_score"] for r in done), 1) if done else 0.0,
        "high_issues": sum(r["issues"]["high"] for r in done),
        "terminology_issues": sum(r["terminology_issues"] for r in done),
        "number_issues": sum(r["number_issues"] for r in done),
        "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
    }
    return {"label": label, "model": settings.model_translate, "effort": settings.effort_translate,
            "prompt_version": PROMPT_VERSION, "judge": judge, "summary": summary, "results": results,
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def compare(a: dict, b: dict) -> list[tuple[str, float, float, float]]:
    rows = []
    for key in ("chrf_mean", "qa_score_mean", "high_issues", "terminology_issues", "number_issues", "complete", "cost_usd"):
        x, y = a["summary"][key], b["summary"][key]
        rows.append((key, x, y, round(y - x, 4)))
    return rows
