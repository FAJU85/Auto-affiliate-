import re

_TEMPLATES = {
    "standard": "Image of {title}",
    "price":    "Image of {title} priced at {price}",
    "brand":    "{brand} {title}",
    "deal":     "{title} on sale for {price}",
    "category": "{category}: {title}",
    "full":     "{brand} {title} — {category}, {price}",
}

_FILLER_WORDS = {"a", "an", "the", "and", "or", "of", "for", "with", "in", "on", "at"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip())


def _title_case(s: str) -> str:
    words = s.split()
    return " ".join(
        w.capitalize() if i == 0 or w.lower() not in _FILLER_WORDS else w.lower()
        for i, w in enumerate(words)
    )


def generate_alt_text(
    title: str,
    brand: str = "",
    category: str = "",
    price: str = "",
) -> str:
    parts = []
    if brand:
        parts.append(_clean(brand))
    parts.append(_clean(title))
    if category:
        parts.append(f"({_clean(category)})")
    if price:
        parts.append(f"— {_clean(price)}")
    return " ".join(parts)


def generate_caption(
    title: str,
    template: str = "standard",
    brand: str = "",
    category: str = "",
    price: str = "",
    max_length: int = 125,
) -> str:
    tpl = _TEMPLATES.get(template, _TEMPLATES["standard"])
    filled = tpl.format(
        title=_clean(title),
        brand=_clean(brand) or "Brand",
        category=_clean(category) or "Product",
        price=_clean(price) or "—",
    )
    caption = _title_case(filled)
    if len(caption) > max_length:
        caption = caption[:max_length - 1].rstrip() + "…"
    return caption


def caption_variants(
    title: str,
    brand: str = "",
    category: str = "",
    price: str = "",
) -> dict[str, str]:
    return {
        name: generate_caption(title, template=name, brand=brand, category=category, price=price)
        for name in _TEMPLATES
    }


def list_templates() -> list[str]:
    return sorted(_TEMPLATES.keys())
