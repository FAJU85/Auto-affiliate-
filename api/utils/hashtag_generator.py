import re
import unicodedata

_STOP = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "this", "that", "be",
    "are", "was", "were", "has", "have", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "not", "no", "as",
    "up", "out", "if", "so", "we", "you", "your", "my", "our",
}

_CATEGORY_TAGS: dict[str, list[str]] = {
    "fashion": ["fashion", "style", "ootd", "outfit"],
    "tech": ["tech", "gadgets", "technology"],
    "electronics": ["electronics", "tech", "gadgets"],
    "beauty": ["beauty", "skincare", "makeup"],
    "health": ["health", "wellness", "selfcare"],
    "fitness": ["fitness", "workout", "gym"],
    "food": ["food", "foodie", "yummy"],
    "travel": ["travel", "wanderlust", "explore"],
    "home": ["homedecor", "interiordesign", "homegoods"],
    "books": ["books", "reading", "bookworm"],
    "toys": ["toys", "kids", "family"],
    "sports": ["sports", "athletic", "active"],
    "pets": ["pets", "petlovers", "animals"],
    "garden": ["garden", "outdoors", "plants"],
    "automotive": ["automotive", "cars", "driving"],
}

_DEAL_TAGS = ["deal", "sale", "discount", "offer", "bargain", "savings"]


def _slug(word: str) -> str:
    word = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w]", "", word.lower())


def generate(
    title: str,
    category: str = "",
    include_deal: bool = False,
    max_tags: int = 10,
) -> list[str]:
    tags: list[str] = []

    # category tags first
    cat_key = _slug(category)
    for key, ctags in _CATEGORY_TAGS.items():
        if key in cat_key or cat_key in key:
            tags.extend(ctags)
            break

    # title keywords
    words = re.findall(r"[a-zA-Z]+", title)
    for w in words:
        slug = _slug(w)
        if slug and slug not in _STOP and len(slug) >= 3:
            tags.append(slug)

    if include_deal:
        tags.extend(_DEAL_TAGS[:3])

    # deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    return ["#" + t for t in unique[:max_tags]]


def format_hashtags(tags: list[str], separator: str = " ") -> str:
    return separator.join(tags)
