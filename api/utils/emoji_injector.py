import re

_CATEGORY_EMOJI: dict[str, list[str]] = {
    "Electronics":  ["⚡", "🎧", "📱", "💻", "🔋"],
    "Beauty":       ["✨", "💄", "💅", "🌸", "🪞"],
    "Fashion":      ["👗", "👟", "👜", "🕶️", "💃"],
    "Home":         ["🏡", "🛋️", "🕯️", "🧹", "🪴"],
    "Sports":       ["🏋️", "🏃", "⚽", "🎯", "💪"],
    "Books":        ["📚", "📖", "✍️", "🧠", "💡"],
    "Toys":         ["🧸", "🎮", "🎁", "🎨", "🎲"],
    "Health":       ["💊", "🌿", "🧘", "❤️", "🍎"],
    "Travel":       ["✈️", "🌍", "🏖️", "🎒", "🗺️"],
    "Food":         ["🍕", "🍳", "🥗", "☕", "🍰"],
    "General":      ["🛒", "💰", "🔥", "⭐", "🎉"],
}

_SENTIMENT_EMOJI: dict[str, str] = {
    "urgency":    "⏰",
    "deal":       "💸",
    "quality":    "⭐",
    "love":       "❤️",
    "new":        "🆕",
    "save":       "💰",
    "free":       "🎁",
    "limited":    "⚠️",
    "exclusive":  "👑",
    "best":       "🏆",
}

_URGENCY_WORDS = {"now", "today", "limited", "hurry", "last", "ends", "only", "quick"}
_DEAL_WORDS = {"save", "deal", "discount", "sale", "off", "cheap", "affordable", "price"}
_QUALITY_WORDS = {"best", "top", "premium", "quality", "excellent", "perfect", "amazing"}


def _detect_sentiment(caption: str) -> str:
    words = set(re.findall(r"\b\w+\b", caption.lower()))
    if words & _URGENCY_WORDS:
        return "urgency"
    if words & _DEAL_WORDS:
        return "deal"
    if words & _QUALITY_WORDS:
        return "quality"
    return "general"


def category_emoji(category: str) -> list[str]:
    return _CATEGORY_EMOJI.get(category, _CATEGORY_EMOJI["General"])


def sentiment_emoji(caption: str) -> str:
    sentiment = _detect_sentiment(caption)
    return _SENTIMENT_EMOJI.get(sentiment, "🛒")


def inject_emoji(caption: str, product: dict, max_emoji: int = 2) -> str:
    if not caption:
        return caption
    existing = len(re.findall(r"[\U00010000-\U0010ffff]|[☀-⛿]|[✀-➿]", caption))
    if existing >= max_emoji:
        return caption
    needed = max_emoji - existing
    cat = product.get("category", "General")
    pool = category_emoji(cat)[:needed]
    sent_emoji = sentiment_emoji(caption)
    if sent_emoji not in pool and needed > 1:
        pool[-1] = sent_emoji
    suffix = " " + " ".join(pool)
    return caption.rstrip() + suffix


def strip_emoji(text: str) -> str:
    return re.sub(r"[\U00010000-\U0010ffff]|[☀-⛿]|[✀-➿]|[⏩-⏳]|[▪-◾]|[☔☕]|[⬅-⬇]|[⬛⬜]|[⭐⭕]", "", text).strip()
