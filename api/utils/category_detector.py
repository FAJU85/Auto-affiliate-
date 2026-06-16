"""Keyword-based product category auto-detection.

Usage:
    from .utils.category_detector import ensure_category
    product = ensure_category(product)
"""

from __future__ import annotations

CATEGORIES: dict[str, list[str]] = {
    "Electronics": [
        "phone", "laptop", "tablet", "computer", "monitor", "keyboard", "mouse",
        "headphone", "earphone", "earbud", "speaker", "camera", "tv", "television",
        "charger", "cable", "usb", "battery", "processor", "gpu", "cpu", "router",
        "smartwatch", "wearable", "drone", "printer", "scanner", "projector",
        "microphone", "webcam", "gaming", "console", "playstation", "xbox",
        "nintendo", "iphone", "android", "samsung", "apple", "pixel", "gadget",
        "electronics", "tech", "device", "wireless", "bluetooth",
    ],
    "Beauty": [
        "lipstick", "mascara", "foundation", "concealer", "eyeshadow", "blush",
        "highlighter", "primer", "skincare", "moisturizer", "serum", "toner",
        "cleanser", "face wash", "sunscreen", "spf", "perfume", "cologne",
        "fragrance", "nail polish", "makeup", "cosmetic", "beauty", "shampoo",
        "conditioner", "hair mask", "hair oil", "lotion", "body wash", "deodorant",
        "razor", "exfoliant", "retinol", "vitamin c", "hyaluronic", "anti-aging",
    ],
    "Fashion": [
        "shirt", "t-shirt", "blouse", "jacket", "coat", "jeans", "trousers",
        "pants", "shorts", "skirt", "dress", "suit", "tie", "scarf", "hat",
        "cap", "sneaker", "shoe", "boot", "sandal", "slipper", "heel",
        "handbag", "purse", "wallet", "belt", "watch", "sunglasses", "glasses",
        "jewelry", "necklace", "bracelet", "ring", "earring", "fashion",
        "clothing", "apparel", "outfit", "style", "hoodie", "sweater",
        "legging", "activewear", "swimsuit", "underwear", "sock",
    ],
    "Home": [
        "sofa", "couch", "chair", "table", "desk", "bed", "mattress", "pillow",
        "blanket", "curtain", "lamp", "light", "rug", "carpet", "shelf",
        "wardrobe", "cabinet", "drawer", "kitchen", "cookware", "pan", "pot",
        "knife", "cutting board", "blender", "mixer", "toaster", "coffee maker",
        "vacuum", "mop", "broom", "cleaning", "detergent", "candle", "diffuser",
        "home decor", "furniture", "bedding", "towel", "shower", "bathroom",
        "storage", "organizer", "frame", "wall art", "plant pot",
    ],
    "Sports": [
        "yoga", "gym", "fitness", "workout", "exercise", "dumbbell", "barbell",
        "treadmill", "bicycle", "bike", "cycling", "running", "jogging",
        "tennis", "basketball", "football", "soccer", "baseball", "golf",
        "swimming", "hiking", "camping", "climbing", "skiing", "snowboard",
        "sport", "athletic", "training", "protein", "supplement", "whey",
        "resistance band", "foam roller", "jump rope", "sports bag",
    ],
    "Books": [
        "book", "novel", "fiction", "non-fiction", "nonfiction", "biography",
        "autobiography", "memoir", "textbook", "guide", "manual", "cookbook",
        "children's book", "comic", "manga", "kindle", "ebook", "audiobook",
        "reading", "literature", "poetry", "thriller", "mystery", "romance",
        "sci-fi", "fantasy", "self-help", "business book", "history book",
    ],
    "Toys": [
        "toy", "lego", "puzzle", "board game", "card game", "doll", "action figure",
        "stuffed animal", "plush", "remote control", "rc car", "model kit",
        "play set", "building block", "clay", "arts and crafts", "kids game",
        "children", "baby toy", "infant", "toddler toy", "educational toy",
    ],
    "Health": [
        "vitamin", "supplement", "probiotic", "omega", "zinc", "magnesium",
        "medicine", "pharmacy", "health", "wellness", "medical", "bandage",
        "first aid", "thermometer", "blood pressure", "glucose", "pain relief",
        "sleep aid", "melatonin", "immunity", "detox", "herbal", "natural remedy",
        "dental", "toothbrush", "toothpaste", "floss", "mouthwash",
    ],
    "Travel": [
        "luggage", "suitcase", "backpack", "travel bag", "carry-on", "passport",
        "travel pillow", "travel adapter", "portable charger", "hotel",
        "flight", "airline", "trip", "vacation", "holiday", "tour", "cruise",
        "travel", "adventure", "destination", "booking", "airbnb", "hostel",
        "travel insurance", "packing", "itinerary",
    ],
    "Food": [
        "food", "snack", "chocolate", "candy", "coffee", "tea", "juice",
        "protein bar", "granola", "cereal", "pasta", "rice", "sauce",
        "spice", "seasoning", "olive oil", "cooking oil", "vinegar",
        "nuts", "dried fruit", "organic", "vegan", "gluten-free", "keto",
        "meal kit", "recipe", "ingredient", "grocery", "beverage", "drink",
        "wine", "beer", "spirits", "cheese", "bread", "baking",
    ],
}


def detect_category(product: dict) -> str:
    """Return the best-matching category name for a product, or 'General'."""
    text = " ".join([
        (product.get("name") or ""),
        (product.get("description") or ""),
    ]).lower()

    best_category = "General"
    best_count = 0

    for category, keywords in CATEGORIES.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_category = category

    return best_category


def ensure_category(product: dict) -> dict:
    """Return a copy of product with 'category' set.

    Preserves an existing non-empty category value; otherwise calls detect_category.
    Never mutates the input dict.
    """
    result = dict(product)
    if not result.get("category"):
        result["category"] = detect_category(result)
    return result
