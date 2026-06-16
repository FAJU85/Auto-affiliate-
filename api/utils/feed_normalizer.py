import re
from typing import Any


_TITLE_FIELDS = ("title", "name", "product_name", "ProductName", "product_title", "item_name")
_PRICE_FIELDS = ("price", "Price", "sale_price", "current_price", "offer_price", "cost")
_IMAGE_FIELDS = ("image", "image_url", "img", "thumbnail", "picture", "photo", "ImageUrl")
_URL_FIELDS = ("url", "link", "affiliate_url", "product_url", "buy_url", "Url", "Link")
_DESC_FIELDS = ("description", "desc", "summary", "short_description", "details", "body")
_CAT_FIELDS = ("category", "cat", "department", "type", "genre", "Category")
_BRAND_FIELDS = ("brand", "Brand", "manufacturer", "vendor", "seller")
_ID_FIELDS = ("id", "product_id", "sku", "asin", "item_id", "pid")


def _first(d: dict, keys: tuple) -> Any:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _clean_price(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.,]", "", str(raw)).replace(",", ".")
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "", cleaned.count(".") - 1)
        return round(float(cleaned), 2)
    except Exception:
        return None


def normalize(item: dict) -> dict:
    return {
        "id": _first(item, _ID_FIELDS) or "",
        "title": _first(item, _TITLE_FIELDS) or "",
        "price": _clean_price(_first(item, _PRICE_FIELDS)),
        "image": _first(item, _IMAGE_FIELDS),
        "url": _first(item, _URL_FIELDS) or "",
        "description": _first(item, _DESC_FIELDS),
        "category": _first(item, _CAT_FIELDS),
        "brand": _first(item, _BRAND_FIELDS),
        "_raw": item,
    }


def normalize_batch(items: list[dict]) -> list[dict]:
    return [normalize(item) for item in items]


def drop_incomplete(items: list[dict], require: list[str] | None = None) -> list[dict]:
    if require is None:
        require = ["title", "url"]
    normalized = normalize_batch(items)
    return [n for n in normalized if all(n.get(f) for f in require)]


def normalization_report(items: list[dict]) -> dict:
    normalized = normalize_batch(items)
    fields = ("title", "price", "image", "url", "description", "category", "brand")
    coverage: dict[str, int] = {}
    for f in fields:
        coverage[f] = sum(1 for n in normalized if n.get(f) is not None and n.get(f) != "")
    return {
        "total": len(normalized),
        "coverage": {f: {"count": c, "pct": round(c / len(normalized) * 100, 1) if normalized else 0}
                     for f, c in coverage.items()},
    }
