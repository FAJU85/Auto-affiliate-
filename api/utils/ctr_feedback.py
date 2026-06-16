"""CTR feedback loop — learn which products and sources drive the most clicks.

Analyses run history to compute per-product and per-source click-through
rates. Returns a boost score (0.0–1.0) that can be added to product scoring
to favour historically high-performing items.

Usage:
    from api.utils.ctr_feedback import ctr_boost_for, ctr_stats

    boost = ctr_boost_for(product_name="Sony WH-1000XM5", source="amazon", runs=runs)
"""

from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple

MIN_IMPRESSIONS = 3  # need at least this many posts to trust the CTR signal


class ProductCTR(NamedTuple):
    name: str
    source: str
    impressions: int
    clicks: int
    ctr: float       # clicks / impressions


def compute_ctr_table(runs: list[dict]) -> list[ProductCTR]:
    """Aggregate click and impression counts per (product_name, source) pair."""
    impressions: dict[tuple[str, str], int] = defaultdict(int)
    clicks: dict[tuple[str, str], int] = defaultdict(int)

    for r in runs:
        if not r.get("success"):
            continue
        name = r.get("product", "")
        source = r.get("productSource", r.get("source", "unknown"))
        if not name:
            continue
        key = (name, source)
        impressions[key] += 1
        clicks[key] += int(r.get("clicks", 0))

    result = []
    for (name, source), imp in impressions.items():
        if imp == 0:
            continue
        clk = clicks[(name, source)]
        result.append(ProductCTR(
            name=name,
            source=source,
            impressions=imp,
            clicks=clk,
            ctr=clk / imp,
        ))

    return sorted(result, key=lambda x: x.ctr, reverse=True)


def ctr_boost_for(product_name: str, source: str, runs: list[dict]) -> float:
    """Return a 0.0–1.0 boost score for a product based on historical CTR.

    Returns 0.5 (neutral) when there is insufficient history.
    Returns >0.5 for above-average CTR, <0.5 for below-average.
    """
    table = compute_ctr_table(runs)
    if not table:
        return 0.5  # no data — neutral

    # Find this specific product
    product_entry = next(
        (p for p in table if p.name == product_name and p.source == source), None
    )
    if product_entry is None or product_entry.impressions < MIN_IMPRESSIONS:
        return 0.5  # insufficient data — neutral

    # Normalise against the max CTR in the table
    max_ctr = max(p.ctr for p in table if p.impressions >= MIN_IMPRESSIONS) or 1.0
    if max_ctr == 0:
        return 0.5

    normalised = product_entry.ctr / max_ctr
    # Map to 0.2–1.0 range so even the lowest performer gets some weight
    return 0.2 + normalised * 0.8


def top_products(runs: list[dict], n: int = 10) -> list[dict]:
    """Return the top-n products by CTR as serialisable dicts."""
    table = [p for p in compute_ctr_table(runs) if p.impressions >= MIN_IMPRESSIONS]
    return [
        {
            "name": p.name,
            "source": p.source,
            "impressions": p.impressions,
            "clicks": p.clicks,
            "ctr": round(p.ctr, 4),
        }
        for p in table[:n]
    ]


def source_ctr_summary(runs: list[dict]) -> list[dict]:
    """Return per-source CTR summary (aggregated across all products)."""
    impressions: dict[str, int] = defaultdict(int)
    clicks: dict[str, int] = defaultdict(int)

    for r in runs:
        if not r.get("success"):
            continue
        source = r.get("productSource", r.get("source", "unknown"))
        impressions[source] += 1
        clicks[source] += int(r.get("clicks", 0))

    result = []
    for source, imp in impressions.items():
        clk = clicks[source]
        result.append({
            "source": source,
            "impressions": imp,
            "clicks": clk,
            "ctr": round(clk / imp, 4) if imp else 0.0,
        })

    return sorted(result, key=lambda x: x["ctr"], reverse=True)


def ctr_summary(runs: list[dict]) -> dict:
    """Full CTR summary for the /api/ctr-stats endpoint."""
    table = compute_ctr_table(runs)
    trusted = [p for p in table if p.impressions >= MIN_IMPRESSIONS]

    total_impressions = sum(p.impressions for p in table)
    total_clicks = sum(p.clicks for p in table)
    overall_ctr = total_clicks / total_impressions if total_impressions else 0.0

    return {
        "overall_ctr": round(overall_ctr, 4),
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "top_products": top_products(runs),
        "by_source": source_ctr_summary(runs),
        "trusted_products": len(trusted),
        "min_impressions_threshold": MIN_IMPRESSIONS,
    }
