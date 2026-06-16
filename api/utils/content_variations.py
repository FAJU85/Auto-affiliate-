"""Content variation engine — generates template-based captions for 3 persuasion angles."""

from __future__ import annotations

ANGLES: list[str] = ["price", "benefit", "curiosity"]

_CTAS = ["Get it now!", "Shop today!", "Don't miss out!", "Grab yours!", "Check it out!"]


def _pick_cta(name: str) -> str:
    return _CTAS[hash(name) % len(_CTAS)]


def generate_variation(product: dict, angle: str) -> str:
    """Return a template-based caption for the given angle."""
    name = product.get("name") or product.get("title") or "this product"
    category = product.get("category") or "lifestyle"
    price = product.get("price")
    cta = _pick_cta(name)

    if angle == "price":
        if price:
            return f"Save big on {name}! Now just {price}. {cta}"
        return f"Amazing deal on {name}! {cta}"

    if angle == "benefit":
        return f"Upgrade your {category} game with {name}. {cta}"

    if angle == "curiosity":
        return f"Looking for the best {category} deal? {name} might surprise you. {cta}"

    raise ValueError(f"Unknown angle: {angle!r}")


def generate_all_variations(product: dict) -> dict[str, str]:
    """Return a dict mapping each angle to its generated caption."""
    return {angle: generate_variation(product, angle) for angle in ANGLES}


def best_variation(
    product: dict, runs: list[dict] | None = None
) -> tuple[str, str]:
    """Return (angle, caption) — picks the angle with highest avg clicks from run history.

    Falls back to 'benefit' when no run history is available.
    """
    if not runs:
        angle = "benefit"
        return angle, generate_variation(product, angle)

    # Aggregate clicks per angle across run history.
    totals: dict[str, int] = {a: 0 for a in ANGLES}
    counts: dict[str, int] = {a: 0 for a in ANGLES}
    for run in runs:
        a = run.get("angle")
        clicks = run.get("clicks", 0)
        if a in totals:
            totals[a] += clicks
            counts[a] += 1

    # Compute averages; angles with no data default to 0.
    avgs = {a: (totals[a] / counts[a] if counts[a] else 0) for a in ANGLES}
    best_angle = max(avgs, key=lambda a: avgs[a])
    return best_angle, generate_variation(product, best_angle)
