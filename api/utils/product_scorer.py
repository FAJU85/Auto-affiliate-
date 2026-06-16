import math
from datetime import datetime, timezone


def _parse_price(price) -> float | None:
    if price is None:
        return None
    try:
        return float(str(price).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def score_product(
    product: dict,
    clicks: int = 0,
    last_posted_hours: float | None = None,
    weight_price: float = 0.25,
    weight_clicks: float = 0.35,
    weight_freshness: float = 0.25,
    weight_has_image: float = 0.15,
) -> dict:
    scores: dict[str, float] = {}

    price = _parse_price(product.get("price") or product.get("Price"))
    if price is not None and price > 0:
        scores["price"] = max(0.0, 1.0 - (price / 200.0))
    else:
        scores["price"] = 0.5

    scores["clicks"] = min(1.0, math.log1p(clicks) / math.log1p(100))

    if last_posted_hours is None:
        scores["freshness"] = 1.0
    elif last_posted_hours >= 48:
        scores["freshness"] = 1.0
    elif last_posted_hours >= 24:
        scores["freshness"] = 0.5
    else:
        scores["freshness"] = 0.0

    has_image = bool(
        product.get("image") or product.get("image_url")
        or product.get("img") or product.get("thumbnail")
    )
    scores["has_image"] = 1.0 if has_image else 0.0

    total = (
        scores["price"] * weight_price
        + scores["clicks"] * weight_clicks
        + scores["freshness"] * weight_freshness
        + scores["has_image"] * weight_has_image
    )

    return {
        "score": round(total, 4),
        "breakdown": {k: round(v, 4) for k, v in scores.items()},
    }


def rank_products(
    products: list[dict],
    clicks_map: dict[str, int] | None = None,
    freshness_map: dict[str, float] | None = None,
) -> list[dict]:
    clicks_map = clicks_map or {}
    freshness_map = freshness_map or {}
    scored = []
    for p in products:
        pid = str(p.get("id") or p.get("product_id") or "")
        result = score_product(
            p,
            clicks=clicks_map.get(pid, 0),
            last_posted_hours=freshness_map.get(pid),
        )
        scored.append({**p, "score": result["score"], "score_breakdown": result["breakdown"]})
    return sorted(scored, key=lambda x: x["score"], reverse=True)
