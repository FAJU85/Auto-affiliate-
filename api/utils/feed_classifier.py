import re

_CATEGORIES: dict[str, list[str]] = {
    "fashion": ["shirt", "dress", "shoes", "boots", "jacket", "coat", "jeans", "pants", "skirt", "hat", "bag", "purse", "sneakers", "clothing", "apparel", "wear", "fashion"],
    "electronics": ["phone", "laptop", "tablet", "headphones", "speaker", "camera", "tv", "monitor", "keyboard", "mouse", "cable", "charger", "battery", "gadget", "electronic"],
    "beauty": ["cream", "serum", "moisturizer", "lipstick", "mascara", "foundation", "perfume", "shampoo", "conditioner", "skincare", "makeup", "beauty", "cosmetic"],
    "health": ["vitamin", "supplement", "protein", "probiotic", "omega", "collagen", "health", "wellness", "medical", "first aid", "fitness tracker"],
    "fitness": ["dumbbell", "yoga", "gym", "workout", "exercise", "resistance band", "treadmill", "bicycle", "weights", "kettlebell", "fitness"],
    "food": ["snack", "chocolate", "coffee", "tea", "spice", "sauce", "organic", "gluten", "protein bar", "food", "drink", "beverage", "nutrition"],
    "home": ["pillow", "blanket", "curtain", "lamp", "shelf", "storage", "organizer", "kitchen", "cookware", "bedding", "furniture", "decor", "home"],
    "garden": ["plant", "seed", "fertilizer", "soil", "pot", "garden", "outdoor", "lawn", "tool", "shovel", "hose"],
    "toys": ["toy", "game", "puzzle", "lego", "doll", "action figure", "board game", "kids", "children", "baby"],
    "books": ["book", "novel", "guide", "manual", "textbook", "kindle", "ebook", "reading"],
    "sports": ["ball", "racket", "helmet", "gloves", "jersey", "cleats", "sport", "athletic", "swim", "run", "golf", "tennis", "soccer", "basketball"],
    "automotive": ["car", "truck", "tire", "oil", "brake", "engine", "automotive", "vehicle", "motor", "dashboard", "seat cover"],
    "pets": ["dog", "cat", "pet", "collar", "leash", "food bowl", "litter", "aquarium", "bird", "fish tank", "treat"],
    "travel": ["luggage", "suitcase", "backpack", "travel", "passport", "adapter", "pillow neck", "map", "hotel"],
}

_DEFAULT = "general"


def _tokens(text: str) -> str:
    return re.sub(r"[^\w\s]", " ", text.lower())


def classify(title: str, description: str = "") -> str:
    combined = _tokens(f"{title} {description}")
    scores: dict[str, int] = {}
    for cat, keywords in _CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score:
            scores[cat] = score
    return max(scores, key=lambda c: scores[c]) if scores else _DEFAULT


def classify_batch(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        cat = classify(
            item.get("title", "") or item.get("name", ""),
            item.get("description", "") or item.get("desc", ""),
        )
        result.append({**item, "category": cat})
    return result


def category_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        cat = item.get("category") or classify(
            item.get("title", "") or item.get("name", ""),
            item.get("description", ""),
        )
        counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
