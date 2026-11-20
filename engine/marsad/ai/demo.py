"""Model-free responses for local demos and end-to-end tests (MARSAD_LLM_BACKEND=fake).

Demo articles get their hand-made Arabic; anything else gets clearly labelled placeholder text,
which the QA step will (correctly) flag."""

import json
from importlib import resources

DEMO = json.loads(resources.files("marsad.data").joinpath("demo_articles.json").read_text(encoding="utf-8"))
_BY_TITLE = {a["title_en"]: a for a in DEMO["articles"]}
PLACEHOLDER = "نص تجريبي: لم يُستدعَ نموذج لغوي في وضع العرض التجريبي (الفقرة {id})."


def demo_handler(task: str, payload: dict) -> dict:
    item = _BY_TITLE.get(payload.get("title", "").strip())
    if task == "classify":
        if item:
            return item["classification"]
        return {"topics": ["strategy-theory"], "regions": ["global"], "doc_type": "commentary", "importance": 3,
                "keywords_en": []}
    if task == "summarize":
        if item:
            return item["summary"]
        title = payload.get("title", "")
        return {"title_ar": f"عنوان تجريبي: {title}", "dek_ar": "ملخص تجريبي دون نموذج لغوي.",
                "thesis_ar": "أطروحة تجريبية.", "key_points_ar": ["نقطة تجريبية."], "evidence_ar": "",
                "recommendations_ar": [], "significance_ar": "", "quotes": [], "new_terms": []}
    if task == "translate":
        known = item.get("paragraphs_ar") if item else None
        return {"paragraphs": [{"id": p["id"], "ar": known[p["id"]] if known and p["id"] < len(known)
                                else PLACEHOLDER.format(id=p["id"])} for p in payload["paragraphs"]],
                "notes": []}
    if task == "qa_judge":
        return {"issues": []}
    if task == "dossier_intro":
        n = len(payload.get("items", []))
        return {"intro_ar": f"مقدمة تجريبية للملف «{payload.get('title_ar', '')}» تجمع {n} مواد. "
                            "كُتبت دون نموذج لغوي في وضع العرض التجريبي، وتُستبدل بمقدمة يراجعها المحرر."}
    if task == "trend_narrative":
        total = payload.get("total", 0)
        return {"narrative_ar": f"قراءة تجريبية لإحصاءات الشهر: رُصدت {total} مادة. "
                                "كُتبت دون نموذج لغوي في وضع العرض التجريبي."}
    raise ValueError(f"unknown task {task}")
