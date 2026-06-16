import hashlib
import re
import unicodedata


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fingerprint(text: str) -> str:
    normalized = _normalize(text)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _shingles(text: str, k: int = 4) -> set[str]:
    words = _normalize(text).split()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def similarity(a: str, b: str, k: int = 4) -> float:
    sa, sb = _shingles(a, k), _shingles(b, k)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def is_duplicate(text: str, seen: list[str], threshold: float = 0.8) -> bool:
    return any(similarity(text, s) >= threshold for s in seen)


def deduplicate(texts: list[str], threshold: float = 0.8) -> list[str]:
    kept: list[str] = []
    for t in texts:
        if not is_duplicate(t, kept, threshold):
            kept.append(t)
    return kept
