"""Product scoring — rank candidate products by revenue potential."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

_IDEAL_PRICE_MIN = 30.0
_IDEAL_PRICE_MAX = 300.0
_COMMISSION_EXCELLENT = 10.0
_COMMISSION_GOOD = 5.0
_COMMISSION_OK = 2.0


@dataclass
class ProductScore:
    commission: float
    price_band: float
    has_image: float
    description: float
    freshness: float = 1.0

    @property
    def total(self) -> float:
        return (
            self.commission * 0.35
            + self.price_band * 0.25
            + self.has_image * 0.20
            + self.description * 0.10
            + self.freshness * 0.10
        )

    def __str__(self) -> str:
        bar = "█" * int(self.total * 10) + "░" * (10 - int(self.total * 10))
        return (
            f"[{bar}] {self.total:.0%}  "
            f"commission={self.commission:.0%}  price={self.price_band:.0%}  "
            f"image={self.has_image:.0%}  desc={self.description:.0%}  fresh={self.freshness:.0%}"
        )


def score_product(product: dict, recently_posted: set | None = None) -> ProductScore:
    rate = float(product.get("commissionRate") or 0)
    if rate >= _COMMISSION_EXCELLENT:
        commission_score = 1.0
    elif rate >= _COMMISSION_GOOD:
        commission_score = 0.7
    elif rate >= _COMMISSION_OK:
        commission_score = 0.4
    elif rate > 0:
        commission_score = 0.2
    else:
        commission_score = 0.5

    price = float(product.get("price") or 0)
    if price <= 0:
        price_score = 0.3
    elif _IDEAL_PRICE_MIN <= price <= _IDEAL_PRICE_MAX:
        price_score = 1.0
    elif price < _IDEAL_PRICE_MIN:
        price_score = max(0.3, price / _IDEAL_PRICE_MIN)
    else:
        overage = price - _IDEAL_PRICE_MAX
        price_score = max(0.3, 1.0 - (overage / 1000))

    has_image = bool(
        product.get("imageUrl") or product.get("imageSearch")
        or product.get("image") or product.get("image_url")
        or product.get("img") or product.get("thumbnail")
    )
    image_score = 1.0 if has_image else 0.0

    desc = str(product.get("description") or product.get("name") or "")
    desc_len = len(desc)
    if desc_len >= 100:
        desc_score = 1.0
    elif desc_len >= 50:
        desc_score = 0.7
    elif desc_len >= 20:
        desc_score = 0.4
    else:
        desc_score = 0.1

    if recently_posted is None:
        freshness_score = 1.0
    else:
        name = str(product.get("name") or product.get("title") or "")
        pid = str(product.get("id") or product.get("product_id") or "")
        freshness_score = 0.0 if (name in recently_posted or pid in recently_posted) else 1.0

    return ProductScore(
        commission=commission_score,
        price_band=price_score,
        has_image=image_score,
        description=desc_score,
        freshness=freshness_score,
    )


def pick_best(products: list[dict], recently_posted: set | None = None) -> dict | None:
    if not products:
        return None
    if len(products) == 1:
        return products[0]
    return max(products, key=lambda p: score_product(p, recently_posted).total)


def rank_products(products: list[dict]) -> list[tuple[dict, ProductScore]]:
    scored = [(p, score_product(p)) for p in products]
    scored.sort(key=lambda x: x[1].total, reverse=True)
    return scored


def pick_best_with_freshness(
    products: list[dict],
    runs: list[dict],
    freshness_hours: int = 6,
) -> dict | None:
    if not products:
        return None
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=freshness_hours)
    recently_posted: set[str] = set()
    for r in runs:
        try:
            ts = datetime.fromisoformat(r.get("timestamp", "").replace("Z", "+00:00"))
            if ts >= cutoff:
                for field_name in ("product_id", "id", "name"):
                    val = str(r.get(field_name) or "")
                    if val:
                        recently_posted.add(val)
        except Exception:
            pass
    return pick_best(products, recently_posted)
