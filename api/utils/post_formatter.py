import re

_LIMITS = {
    "twitter": 280,
    "bluesky": 300,
    "mastodon": 500,
    "instagram": 2200,
    "facebook": 63206,
    "threads": 500,
    "tumblr": 4096,
}

_TEMPLATES = {
    "standard": "{emoji} {title}\n\n{price_line}\n\n{description}\n\n{url}\n\n{hashtags}",
    "compact": "{emoji} {title} — {price_line} {url}",
    "deal": "DEAL: {title}\n{price_line}\n{url}\n{hashtags}",
    "minimal": "{title}\n{url}",
}

_DEAL_EMOJIS = ["🔥", "⚡", "💥", "🎯", "✨", "🛒", "💰", "🏷️"]


def _truncate(text: str, max_len: int, suffix: str = "…") -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def _price_line(price: float | str | None, original_price: float | None = None, currency: str = "USD") -> str:
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    sym = symbols.get(currency, currency + " ")
    if price is None:
        return ""
    try:
        p = float(price)
        if original_price and float(original_price) > p:
            discount = round((float(original_price) - p) / float(original_price) * 100)
            return f"{sym}{p:.2f} (was {sym}{float(original_price):.2f}, {discount}% off)"
        return f"{sym}{p:.2f}"
    except (ValueError, TypeError):
        return str(price)


def format_post(
    product: dict,
    platform: str = "twitter",
    template: str = "standard",
    hashtags: list[str] | None = None,
    emoji: str | None = None,
) -> str:
    if template not in _TEMPLATES:
        raise ValueError(f"Template must be one of {list(_TEMPLATES)}")
    limit = _LIMITS.get(platform.lower(), 280)
    title = product.get("title", "")
    url = product.get("url", "")
    description = product.get("description", "")
    price = product.get("price")
    original = product.get("original_price")
    currency = product.get("currency", "USD")
    price_line = _price_line(price, original, currency)
    emoji_str = emoji or _DEAL_EMOJIS[hash(title) % len(_DEAL_EMOJIS)]
    tag_str = " ".join(f"#{t.lstrip('#')}" for t in (hashtags or []))
    tmpl = _TEMPLATES[template]
    text = tmpl.format(
        title=title,
        price_line=price_line,
        description=description,
        url=url,
        hashtags=tag_str,
        emoji=emoji_str,
    ).strip()
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return _truncate(text, limit)


def format_batch(
    products: list[dict],
    platform: str = "twitter",
    template: str = "standard",
) -> list[str]:
    return [format_post(p, platform=platform, template=template) for p in products]


def fits_platform(text: str, platform: str) -> bool:
    return len(text) <= _LIMITS.get(platform.lower(), 280)


def format_stats(text: str) -> dict:
    return {
        "length": len(text),
        "lines": text.count("\n") + 1,
        "fits": {p: len(text) <= lim for p, lim in _LIMITS.items()},
    }
