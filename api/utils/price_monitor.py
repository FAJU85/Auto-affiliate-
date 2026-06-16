"""Relative price monitor — ranks products by value score within categories."""

from __future__ import annotations


def _parse_price(raw) -> float:
    """Parse price from various formats (float, int, '$12.99', etc.)."""
    if raw is None:
        return float("inf")
    if isinstance(raw, (int, float)):
        val = float(raw)
        return float("inf") if val <= 0 else val
    # String: strip currency symbols and whitespace
    cleaned = str(raw).replace("$", "").replace("€", "").replace("£", "").replace(",", "").strip()
    try:
        val = float(cleaned)
        return float("inf") if val <= 0 else val
    except ValueError:
        return float("inf")


def _value_score(product: dict) -> float:
    """Compute value score = price / max(commission_rate, 1.0)."""
    price = _parse_price(product.get("price"))
    if price == float("inf"):
        return float("inf")
    commission_rate = product.get("commission_rate", 1.0)
    if not isinstance(commission_rate, (int, float)) or commission_rate <= 0:
        commission_rate = 1.0
    return price / commission_rate


def rank_by_value(products: list[dict]) -> list[dict]:
    """Return products sorted ascending by value score (lower = better value).

    Each returned dict gains a ``_value_score`` key.
    """
    scored = []
    for p in products:
        copy = dict(p)
        copy["_value_score"] = _value_score(p)
        scored.append(copy)
    scored.sort(key=lambda x: (x["_value_score"] == float("inf"), x["_value_score"]))
    return scored


def best_value(products: list[dict]) -> dict | None:
    """Return the product with the lowest value score, or None if empty."""
    if not products:
        return None
    ranked = rank_by_value(products)
    return ranked[0]


def group_by_category(products: list[dict]) -> dict[str, list[dict]]:
    """Group products by their ``category`` field (defaults to 'General')."""
    groups: dict[str, list[dict]] = {}
    for p in products:
        cat = p.get("category", "General") or "General"
        groups.setdefault(cat, []).append(p)
    return groups


def best_value_per_category(products: list[dict]) -> dict[str, dict]:
    """Return ``{category: best_value_product}`` for each category."""
    groups = group_by_category(products)
    return {cat: best_value(items) for cat, items in groups.items()}
