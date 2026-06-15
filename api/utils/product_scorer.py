"""Product scoring — rank candidate products by revenue potential.

Score is 0.0–1.0 weighted across four dimensions:

  commission  (40%) — higher affiliate commission = more revenue per sale
  price_band  (30%) — $50–$300 is the impulse-buy sweet spot
  has_image   (20%) — posts with images get 2-3x more clicks
  description (10%) — richer descriptions = better AI captions

Usage:
    from api.utils.product_scorer import score_product, pick_best

    best = pick_best([product_a, product_b, product_c])
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


@dataclass
class ProductScore:
    commission: float   # 0.0–1.0
    price_band: float   # 0.0–1.0
    has_image: float    # 0.0 or 1.0
    description: float  # 0.0–1.0

    @property
    def total(self) -> float:
        return (
            self.commission  * 0.40
            + self.price_band  * 0.30
            + self.has_image   * 0.20
            + self.description * 0.10
        )

    def __str__(self) -> str:
        bar = "█" * int(self.total * 10) + "░" * (10 - int(self.total * 10))
        return (
            f"[{bar}] {self.total:.0%}  "
            f"commission={self.commission:.0%}  price={self.price_band:.0%}  "
            f"image={self.has_image:.0%}  desc={self.description:.0%}"
        )


def score_product(product: dict) -> ProductScore:
    """Score a single product dict. Works with any affiliate network format."""

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
        # No commission data (e.g. SOVRN products don't include rate)
        # Default to mid-tier rather than zero — SOVRN monetizes via link
        commission_score = 0.5

    # ── Price band ────────────────────────────────────────────────────────────
    price = float(product.get("price") or 0)
    if price <= 0:
        price_score = 0.3  # unknown price — some potential
    elif _IDEAL_PRICE_MIN <= price <= _IDEAL_PRICE_MAX:
        price_score = 1.0
    elif price < _IDEAL_PRICE_MIN:
        # Very cheap items: low commission value, though conversion is higher
        price_score = max(0.3, price / _IDEAL_PRICE_MIN)
    else:
        # Expensive items: high commission per sale but lower conversion rate
        # Score decays but never below 0.3 (luxury items still worthwhile)
        overage = price - _IDEAL_PRICE_MAX
        price_score = max(0.3, 1.0 - (overage / 1000))

    # ── Has image ─────────────────────────────────────────────────────────────
    has_image = bool(
        product.get("imageUrl")
        or product.get("imageSearch")  # SOVRN products have imageSearch for lookup
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

    return ProductScore(
        commission=commission_score,
        price_band=price_score,
        has_image=image_score,
        description=desc_score,
    )


def pick_best(products: list[dict]) -> dict | None:
    """Return the highest-scoring product from a list. Returns None if list empty."""
    if not products:
        return None
    if len(products) == 1:
        return products[0]
    return max(products, key=lambda p: score_product(p).total)


def rank_products(products: list[dict]) -> list[tuple[dict, ProductScore]]:
    """Return products sorted by score descending, with their scores."""
    scored = [(p, score_product(p)) for p in products]
    scored.sort(key=lambda x: x[1].total, reverse=True)
    return scored
