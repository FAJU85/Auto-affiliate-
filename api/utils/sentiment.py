import re

_POSITIVE = {
    "amazing", "awesome", "best", "beautiful", "brilliant", "cheap", "deal",
    "discount", "easy", "excellent", "fantastic", "fast", "free", "fresh",
    "good", "great", "happy", "incredible", "love", "lovely", "new", "nice",
    "perfect", "popular", "premium", "recommended", "reliable", "sale",
    "saving", "special", "stunning", "super", "top", "trusted", "unique",
    "value", "wonderful", "wow",
}

_NEGATIVE = {
    "bad", "awful", "broken", "cheap", "complicated", "dangerous", "defective",
    "disappointing", "difficult", "dull", "expensive", "fake", "flimsy",
    "frustrating", "heavy", "horrible", "inferior", "limited", "mediocre",
    "missing", "outdated", "overpriced", "poor", "problematic", "recalled",
    "risky", "slow", "terrible", "ugly", "unreliable", "waste", "worst",
}

_INTENSIFIERS = {"very", "extremely", "incredibly", "absolutely", "so", "really", "quite"}
_NEGATORS = {"not", "no", "never", "without", "don't", "doesn't", "isn't", "wasn't", "hardly"}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def analyze(text: str) -> dict:
    tokens = _tokenize(text)
    pos = neg = 0
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        prev = tokens[i - 1] if i > 0 else ""
        prev2 = tokens[i - 2] if i > 1 else ""
        intensifier = prev in _INTENSIFIERS or prev2 in _INTENSIFIERS
        negated = prev in _NEGATORS or prev2 in _NEGATORS
        weight = 2 if intensifier else 1

        if tok in _POSITIVE:
            if negated:
                neg += weight
            else:
                pos += weight
        elif tok in _NEGATIVE:
            if negated:
                pos += weight
            else:
                neg += weight
        i += 1

    total = pos + neg
    score = round((pos - neg) / total, 3) if total else 0.0

    if score > 0.1:
        label = "positive"
    elif score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return {
        "score": score,
        "label": label,
        "positive_signals": pos,
        "negative_signals": neg,
    }


def batch_analyze(texts: list[str]) -> list[dict]:
    return [{"text": t, **analyze(t)} for t in texts]


def sentiment_stats(texts: list[str]) -> dict:
    results = [analyze(t) for t in texts]
    if not results:
        return {"count": 0, "avg_score": 0.0, "positive": 0, "negative": 0, "neutral": 0}
    avg = round(sum(r["score"] for r in results) / len(results), 3)
    return {
        "count": len(results),
        "avg_score": avg,
        "positive": sum(1 for r in results if r["label"] == "positive"),
        "negative": sum(1 for r in results if r["label"] == "negative"),
        "neutral": sum(1 for r in results if r["label"] == "neutral"),
    }
