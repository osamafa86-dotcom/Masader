"""JSON schemas for structured outputs. Limits the schema cannot express are enforced in code."""

from importlib import resources

import yaml

_TAXONOMY = yaml.safe_load(resources.files("marsad.data").joinpath("taxonomy.yaml").read_text(encoding="utf-8"))
TOPICS = list(_TAXONOMY["topic"])
REGIONS = list(_TAXONOMY["region"])
DOC_TYPES = list(_TAXONOMY["doc_type"])


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


STR = {"type": "string"}
STR_LIST = {"type": "array", "items": STR}

CLASSIFICATION = _obj({
    "topics": {"type": "array", "items": {"type": "string", "enum": TOPICS}},
    "regions": {"type": "array", "items": {"type": "string", "enum": REGIONS}},
    "doc_type": {"type": "string", "enum": DOC_TYPES},
    "importance": {"type": "integer"},
    "keywords_en": STR_LIST,
})

SUMMARY = _obj({
    "title_ar": STR,
    "dek_ar": STR,
    "thesis_ar": STR,
    "key_points_ar": STR_LIST,
    "evidence_ar": STR,
    "recommendations_ar": STR_LIST,
    "significance_ar": STR,
    "quotes": {"type": "array", "items": _obj({"en": STR, "ar": STR})},
    "new_terms": {"type": "array", "items": _obj({"en": STR, "ar": STR})},
})

TRANSLATION = _obj({
    "paragraphs": {"type": "array", "items": _obj({"id": {"type": "integer"}, "ar": STR})},
    "notes": {"type": "array", "items": _obj({"id": {"type": "integer"}, "note_ar": STR})},
})

JUDGE = _obj({
    "issues": {"type": "array", "items": _obj({
        "paragraph_id": {"type": "integer"},
        "kind": {"type": "string", "enum": ["omission", "addition", "mistranslation", "number", "terminology", "style"]},
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "detail_ar": STR,
    })},
})
