import re

BYLINE = re.compile(r"^(by|written by)\s+[A-Z][\w.'-]+(\s+[A-Z][\w.'-]+){0,4}(\s*(,|and)\s*[A-Z][\w.'-]+(\s+[A-Z][\w.'-]+){0,4})*\.?$", re.I)
BOILERPLATE = re.compile(
    r"^(share( this)?|subscribe|sign up|follow us|related( articles)?|read more|advertisement|image:|photo:)\b", re.I
)


def clean_paragraphs(paragraphs: list[str]) -> list[str]:
    out: list[str] = []
    for p in paragraphs:
        p = re.sub(r"\s+", " ", p).strip()
        if not p or BYLINE.match(p) or (BOILERPLATE.match(p) and len(p.split()) < 15):
            continue
        if out and out[-1] == p:
            continue
        out.append(p)
    return out
