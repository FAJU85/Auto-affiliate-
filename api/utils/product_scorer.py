"""Product scoring — rank candidate products by revenue potential.

Score is 0.0–1.0 weighted across five dimensions:

  commission  (35%) — higher affiliate commission = more revenue per sale
  price_band  (25%) — $50–$300 is the impulse-buy sweet spot
  has_image   (20%) — posts with images get 2-3x more clicks
  description (10%) — richer descriptions = better AI captions
  freshness   (10%) — products not posted recently get a novelty boost

Usage:
    from api.utils.product_scorer import score_product, pick_best, pick_best_with_freshness

    best = pick_best_with_freshness([product_a, product_b], recently_posted={"Widget"})
"""

from __future__ import annotations

from dataclasses import dataclass

# Products in this price range convert at 3-5x the rate of items outside it
_IDEAL_PRICE_MIN = 30.0
_IDEAL_PRICE_MAX = 300.0

# Commission rates considered excellent (network-specific context)
# SOVRN/Amazon ~4-8%, TakeAds up to 20%, Admitad 5-15%
_COMMISSION_EXCELLENT = 10.0  # %
_COMMISSION_GOOD = 5.0        # %
_COMMISSION_OK = 2.0          # %

# Freshness: products last posted this many hours ago get zero freshness bonus
_FRESHNESS_WINDOW_HOURS = 24


@dataclass
class ProductScore:
    commission: float   # 0.0–1.0
    price_band: float   # 0.0–1.0
    has_image: float    # 0.0 or 1.0
    description: float  # 0.0–1.0
    freshness: float = 1.0  # 0.0 or 1.0 — 1.0 means not recently posted

    @property
    def total(self) -> float:
        return (
            self.commission  * 0.35
            + self.price_band  * 0.25
            + self.has_image   * 0.20
            + self.description * 0.10
            + self.freshness   * 0.10
        )

    def __str__(self) -> str:
        bar = "█" * int(self.total * 10) + "░" * (10 - int(self.total * 10))
        return (
            f"[{bar}] {self.total:.0%}  "
            f"commission={self.commission:.0%}  price={self.price_band:.0%}  "
            f"image={self.has_image:.0%}  desc={self.description:.0%}  "
            f"fresh={self.freshness:.0%}"
        )


def score_product(product: dict, recently_posted: set[str] | None = None) -> ProductScore:
    """Score a single product dict. Works with any affiliate network format.

    Args:
        product: product dict from any affiliate network
        recently_posted: set of product names posted within the dedup window
    """

    # ── Commission ────────────────────────────────────────────────────────────
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

    # ── Price band ────────────────────────────────────────────────────────────
    try:
        price = float(str(product.get("price") or 0).lstrip("$").replace(",", ""))
    except (ValueError, TypeError):
        price = 0.0
    if price <= 0:
        price_score = 0.3
    elif _IDEAL_PRICE_MIN <= price <= _IDEAL_PRICE_MAX:
        price_score = 1.0
    elif price < _IDEAL_PRICE_MIN:
        price_score = max(0.3, price / _IDEAL_PRICE_MIN)
    else:
        overage = price - _IDEAL_PRICE_MAX
        price_score = max(0.3, 1.0 - (overage / 1000))

    # ── Has image ─────────────────────────────────────────────────────────────
    has_image = bool(
        product.get("imageUrl")
        or product.get("imageSearch")
    )
    image_score = 1.0 if has_image else 0.0

    # ── Description quality ───────────────────────────────────────────────────
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

    # ── Freshness ─────────────────────────────────────────────────────────────
    name = product.get("name", "")
    if recently_posted is not None and name in recently_posted:
        freshness_score = 0.0  # penalise recently posted products
    else:
        freshness_score = 1.0

    return ProductScore(
        commission=commission_score,
        price_band=price_score,
        has_image=image_score,
        description=desc_score,
        freshness=freshness_score,
    )


def pick_best(products: list[dict], recently_posted: set[str] | None = None) -> dict | None:
    """Return the highest-scoring product. Accepts optional freshness context."""
    if not products:
        return None
    if len(products) == 1:
        return products[0]
    return max(products, key=lambda p: score_product(p, recently_posted).total)


def pick_best_with_freshness(products: list[dict], runs: list[dict]) -> dict | None:
    """Pick the best product, penalising those posted in the last DEDUP_TTL_HOURS."""
    from .metrics import DEDUP_TTL_HOURS
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_TTL_HOURS)
    recently_posted: set[str] = set()
    for r in runs:
        if not r.get("success"):
            continue
        ts_str = r.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts > cutoff:
                name = r.get("product", "")
                if name:
                    recently_posted.add(name)
        except (ValueError, TypeError):
            pass

    return pick_best(products, recently_posted=recently_posted)


def rank_products(products: list[dict], recently_posted: set[str] | None = None) -> list[tuple[dict, ProductScore]]:
    """Return products sorted by score descending, with their scores."""
    scored = [(p, score_product(p, recently_posted)) for p in products]
    scored.sort(key=lambda x: x[1].total, reverse=True)
    return scored
