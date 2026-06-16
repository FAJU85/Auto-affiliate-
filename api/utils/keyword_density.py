import re
from collections import Counter

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "it", "this", "that", "be", "are", "was", "were",
    "have", "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "should", "may", "might", "by", "from", "as", "if", "so", "up", "not",
    "you", "your", "i", "my", "we", "our", "its", "their",
}


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"\b[a-z]{3,}\b", text.lower()) if w not in _STOP_WORDS]


def keyword_density(text: str) -> dict[str, float]:
    tokens = _tokenize(text)
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {word: round(count / total, 4) for word, count in counts.most_common(20)}


def coverage_score(caption: str, product: dict) -> float:
    name_terms = set(_tokenize(product.get("name", "")))
    desc_terms = set(_tokenize(product.get("description", "")))
    category_terms = set(_tokenize(product.get("category", "")))
    target = name_terms | desc_terms | category_terms
    if not target:
        return 1.0
    caption_terms = set(_tokenize(caption))
    covered = target & caption_terms
    return round(len(covered) / len(target), 3)


def top_keywords(text: str, n: int = 5) -> list[str]:
    density = keyword_density(text)
    return list(density.keys())[:n]


def keyword_overlap(text_a: str, text_b: str) -> float:
    words_a = set(_tokenize(text_a))
    words_b = set(_tokenize(text_b))
    if not words_a or not words_b:
        return 0.0
    union = words_a | words_b
    intersection = words_a & words_b
    return round(len(intersection) / len(union), 3)
