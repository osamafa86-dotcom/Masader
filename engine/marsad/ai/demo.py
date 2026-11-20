"""Model-free responses for local demos and end-to-end tests (MARSAD_LLM_BACKEND=fake).

Known demo articles get their hand-made Arabic; anything else gets clearly labelled placeholder text,
which the QA step will (correctly) flag."""

import json
from importlib import resources

_DEMO = json.loads(resources.files("marsad.data").joinpath("demo_gray_zone.json").read_text(encoding="utf-8"))
PLACEHOLDER = "نص تجريبي: لم يُستدعَ نموذج لغوي في وضع العرض التجريبي (الفقرة {id})."


def _is_demo(title: str) -> bool:
    return title.strip() == _DEMO["title_en"]


def demo_handler(task: str, payload: dict) -> dict:
    title = payload.get("title", "")
    if task == "classify":
        if _is_demo(title):
            return _DEMO["classification"]
        return {"topics": ["strategy-theory"], "regions": ["global"], "doc_type": "commentary", "importance": 3,
                "keywords_en": []}
    if task == "summarize":
        if _is_demo(title):
            return _DEMO["summary"]
        return {"title_ar": f"عنوان تجريبي: {title}", "dek_ar": "ملخص تجريبي دون نموذج لغوي.",
                "thesis_ar": "أطروحة تجريبية.", "key_points_ar": ["نقطة تجريبية."], "evidence_ar": "",
                "recommendations_ar": [], "significance_ar": "", "quotes": [], "new_terms": []}
    if task == "translate":
        known = _DEMO["paragraphs_ar"] if _is_demo(title) else None
        return {"paragraphs": [{"id": p["id"], "ar": known[p["id"]] if known and p["id"] < len(known)
                                else PLACEHOLDER.format(id=p["id"])} for p in payload["paragraphs"]],
                "notes": []}
    if task == "qa_judge":
        return {"issues": []}
    raise ValueError(f"unknown task {task}")
