import re
from collections import Counter

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "be", "has", "have",
    "it", "its", "this", "that", "these", "those", "as", "so", "if", "do",
    "not", "no", "up", "out", "all", "can", "will", "your", "our", "my",
    "you", "we", "i", "he", "she", "they", "get", "got", "how", "what",
    "new", "now", "free", "just", "more", "than", "also", "very", "any",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z]{3,}\b", text.lower())


def extract_keywords(text: str, max_keywords: int = 10, min_freq: int = 1) -> list[str]:
    tokens = _tokenize(text)
    filtered = [t for t in tokens if t not in _STOPWORDS]
    counts = Counter(filtered)
    return [word for word, freq in counts.most_common(max_keywords) if freq >= min_freq]


def extract_keyphrases(text: str, phrase_len: int = 2, max_phrases: int = 5) -> list[str]:
    tokens = _tokenize(text)
    phrases = []
    for i in range(len(tokens) - phrase_len + 1):
        phrase = tokens[i:i + phrase_len]
        if not any(w in _STOPWORDS for w in phrase):
            phrases.append(" ".join(phrase))
    counts = Counter(phrases)
    return [p for p, _ in counts.most_common(max_phrases)]


def keyword_score(text: str, keywords: list[str]) -> float:
    if not text or not keywords:
        return 0.0
    tokens = set(_tokenize(text))
    matched = sum(1 for k in keywords if k.lower() in tokens)
    return round(matched / len(keywords), 3)


def extract_from_product(product: dict, max_keywords: int = 8) -> dict:
    title = product.get("title", "")
    description = product.get("description", "")
    combined = f"{title} {title} {description}"  # double title for weight
    keywords = extract_keywords(combined, max_keywords=max_keywords)
    keyphrases = extract_keyphrases(combined, max_phrases=3)
    return {
        "keywords": keywords,
        "keyphrases": keyphrases,
        "title_keywords": extract_keywords(title, max_keywords=5),
    }


def keyword_overlap(text_a: str, text_b: str) -> float:
    kw_a = set(extract_keywords(text_a, max_keywords=20))
    kw_b = set(extract_keywords(text_b, max_keywords=20))
    if not kw_a or not kw_b:
        return 0.0
    intersection = kw_a & kw_b
    union = kw_a | kw_b
    return round(len(intersection) / len(union), 3)
