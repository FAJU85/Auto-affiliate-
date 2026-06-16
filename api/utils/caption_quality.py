import re

_CTA_WORDS = {
    "get", "buy", "shop", "save", "grab", "try", "discover", "find", "enjoy",
    "upgrade", "love", "check", "order", "click", "visit", "now", "today",
}

_WEAK_WORDS = {"very", "really", "stuff", "thing", "things", "nice", "good", "great"}

_IDEAL_MIN = 80
_IDEAL_MAX = 200


def _word_count(text: str) -> int:
    return len(text.split())


def _has_cta(text: str) -> bool:
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & _CTA_WORDS)


def _has_punctuation(text: str) -> bool:
    return bool(re.search(r"[.!?]", text))


def _weak_word_ratio(text: str) -> float:
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 0.0
    return sum(1 for w in words if w in _WEAK_WORDS) / len(words)


def score_caption(caption: str) -> dict:
    if not caption:
        return {"total": 0.0, "breakdown": {}}

    length = len(caption)
    wc = _word_count(caption)

    length_score = 1.0 if _IDEAL_MIN <= length <= _IDEAL_MAX else max(0.0, 1.0 - abs(length - _IDEAL_MAX) / _IDEAL_MAX)
    cta_score = 1.0 if _has_cta(caption) else 0.0
    punct_score = 1.0 if _has_punctuation(caption) else 0.3
    weak_score = max(0.0, 1.0 - _weak_word_ratio(caption) * 5)
    word_score = min(1.0, wc / 10) if wc < 10 else 1.0

    breakdown = {
        "length": round(length_score, 3),
        "cta_present": round(cta_score, 3),
        "punctuation": round(punct_score, 3),
        "weak_words": round(weak_score, 3),
        "word_count": round(word_score, 3),
    }
    total = round(
        length_score * 0.25
        + cta_score * 0.35
        + punct_score * 0.15
        + weak_score * 0.15
        + word_score * 0.10,
        3,
    )
    return {"total": total, "breakdown": breakdown}


def is_quality(caption: str, threshold: float = 0.5) -> bool:
    return score_caption(caption)["total"] >= threshold


def rank_captions(captions: list[str]) -> list[tuple[str, float]]:
    scored = [(c, score_caption(c)["total"]) for c in captions]
    return sorted(scored, key=lambda x: x[1], reverse=True)
