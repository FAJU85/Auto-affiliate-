"""Local trend keyword cache mapping product categories to trending search terms."""

CATEGORY_TRENDS: dict[str, list[str]] = {
    "Electronics": [
        "best budget smartphone 2026",
        "wireless earbuds deal",
        "4K monitor sale",
        "gaming laptop under $1000",
        "smart home device",
        "USB-C hub review",
        "portable charger trending",
    ],
    "Beauty": [
        "clean beauty routine",
        "viral skincare serum",
        "SPF moisturizer trending",
        "glass skin tutorial",
        "drugstore makeup dupe",
        "retinol for beginners",
        "tinted lip balm summer",
    ],
    "Fashion": [
        "quiet luxury outfits",
        "summer dress haul",
        "sneaker drop 2026",
        "linen pants trending",
        "capsule wardrobe essentials",
        "thrift flip style",
        "platform sandals viral",
    ],
    "Home": [
        "aesthetic home decor",
        "small space organization",
        "linen bedding review",
        "kitchen gadget must-have",
        "air purifier trending",
        "cozy reading nook ideas",
        "sustainable home products",
    ],
    "Sports": [
        "running shoe 2026",
        "home gym setup budget",
        "yoga mat comparison",
        "protein powder trending",
        "hiking gear essentials",
        "resistance band workout",
        "smartwatch fitness tracker",
    ],
    "Books": [
        "best books 2026",
        "BookTok trending read",
        "self-help bestseller",
        "fantasy novel series",
        "audiobook subscription deal",
        "graphic novel recommendation",
        "nonfiction must-read summer",
    ],
    "Toys": [
        "STEM toy kids trending",
        "outdoor play set sale",
        "puzzle board game family",
        "action figure collectible",
        "sensory toy review",
        "building blocks creative",
        "kids tablet learning",
    ],
    "Health": [
        "magnesium supplement trending",
        "gut health probiotic",
        "collagen powder review",
        "sleep aid natural remedy",
        "fitness recovery tool",
        "vitamin D deficiency fix",
        "mental wellness app",
    ],
    "Travel": [
        "carry-on luggage 2026",
        "travel pillow review",
        "packing cubes trending",
        "budget travel destinations",
        "travel credit card deal",
        "portable wifi hotspot",
        "compression socks long flight",
    ],
    "Food": [
        "viral recipe trending",
        "meal prep container deal",
        "air fryer recipe popular",
        "protein snack review",
        "coffee subscription box",
        "hot sauce trending",
        "zero waste kitchen",
    ],
    "General": [
        "best deal today",
        "trending product 2026",
        "viral find sale",
        "editor's pick discount",
        "limited time offer",
        "top rated item",
        "must-have summer 2026",
    ],
}

_LOWER_MAP: dict[str, str] = {k.lower(): k for k in CATEGORY_TRENDS}


def get_trends_for(category: str, n: int = 3) -> list[str]:
    """Return up to n trending phrases for the given category (case-insensitive).

    Falls back to 'General' if the category is not found.
    """
    key = _LOWER_MAP.get(category.lower(), "General")
    return CATEGORY_TRENDS[key][:n]


def inject_trend(product: dict, trends: list[str] | None = None) -> list[str]:
    """Return trends for a product.

    If trends is provided and non-empty, return as-is.
    Otherwise derive trends from the product's category field.
    """
    if trends:
        return trends
    return get_trends_for(product.get("category", "General"))


def best_trend(product: dict, runs: list[dict] | None = None) -> str:
    """Return a single best trend string for the product.

    If runs are provided, prefer trend phrases that appear in high-click run
    captions. Otherwise return the first trend from get_trends_for.
    """
    candidates = get_trends_for(product.get("category", "General"), n=7)
    if runs:
        high_click = [
            r.get("caption", "") for r in runs if (r.get("clicks") or 0) > 0
        ]
        for phrase in candidates:
            if any(phrase.lower() in caption.lower() for caption in high_click):
                return phrase
    return candidates[0] if candidates else ""
