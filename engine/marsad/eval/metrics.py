"""chrF: character n-gram F-score (Popović 2015), computed on normalised Arabic so diacritics do not count."""

from collections import Counter

from marsad.arabic import normalize_ar


def _ngrams(text: str, n: int) -> Counter:
    return Counter(text[i:i + n] for i in range(len(text) - n + 1))


def chrf(hypothesis: str, reference: str, max_n: int = 6, beta: float = 2.0) -> float:
    hyp = normalize_ar(hypothesis).replace(" ", "")
    ref = normalize_ar(reference).replace(" ", "")
    if not hyp and not ref:
        return 100.0
    if not hyp or not ref:
        return 0.0
    precisions, recalls = [], []
    for n in range(1, max_n + 1):
        h, r = _ngrams(hyp, n), _ngrams(ref, n)
        if not h or not r:
            continue
        match = sum((h & r).values())
        precisions.append(match / sum(h.values()))
        recalls.append(match / sum(r.values()))
    if not precisions:
        return 0.0
    p, r = sum(precisions) / len(precisions), sum(recalls) / len(recalls)
    if p == 0 and r == 0:
        return 0.0
    return round(100 * (1 + beta ** 2) * p * r / (beta ** 2 * p + r), 2)
