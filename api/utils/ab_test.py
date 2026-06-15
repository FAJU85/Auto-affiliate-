"""A/B caption testing tracker.

Each pipeline run is randomly assigned to variant A (standard caption)
or variant B (alternative style). Click-through rates per variant are
tracked so we can determine which language converts better.

Variants:
  A — standard: benefit-led, price mention, punchy CTA
  B — curiosity: question hook, social proof angle, softer CTA

Data: DATA_DIR/ab_test.json
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))

# Variant B system prompt modifier — override the CTA style
VARIANT_B_STYLE = (
    "Write from a social proof / curiosity angle instead of a direct sell. "
    "Open with a hook question or a surprising fact about the product. "
    "End with a softer curiosity CTA like 'See why everyone's talking about it →' "
    "or 'Find out if it's worth it →'. Do NOT use aggressive urgency language."
)

VARIANT_SPLIT = 0.50  # 50/50 split


def _file() -> Path:
    return Path(os.environ.get("DATA_DIR", str(DATA_DIR))) / "ab_test.json"


def _load() -> dict:
    f = _file()
    if not f.exists():
        return {"variants": {"A": {"runs": 0, "clicks": 0}, "B": {"runs": 0, "clicks": 0}},
                "assignments": {}}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {"variants": {"A": {"runs": 0, "clicks": 0}, "B": {"runs": 0, "clicks": 0}},
                "assignments": {}}


def _save(data: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


def assign_variant(tracking_id: str) -> str:
    """Assign a variant to a tracking ID and record the run. Returns 'A' or 'B'."""
    data = _load()
    data.setdefault("variants", {"A": {"runs": 0, "clicks": 0}, "B": {"runs": 0, "clicks": 0}})
    data.setdefault("assignments", {})

    if tracking_id in data["assignments"]:
        return data["assignments"][tracking_id]["variant"]

    variant = "B" if random.random() < VARIANT_SPLIT else "A"
    data["assignments"][tracking_id] = {
        "variant": variant,
        "assigned_at": time.time(),
        "clicks": 0,
    }
    data["variants"][variant]["runs"] = data["variants"][variant].get("runs", 0) + 1
    _save(data)
    return variant


def record_click(tracking_id: str) -> str | None:
    """Record a click for a tracking ID. Returns the variant or None if unknown."""
    data = _load()
    assignment = data.get("assignments", {}).get(tracking_id)
    if not assignment:
        return None

    assignment["clicks"] = assignment.get("clicks", 0) + 1
    variant = assignment["variant"]
    data["variants"][variant]["clicks"] = data["variants"][variant].get("clicks", 0) + 1
    _save(data)
    return variant


def get_results() -> dict:
    """Return A/B test summary with CTR per variant."""
    data = _load()
    variants = data.get("variants", {})
    result = {}
    for name, stats in variants.items():
        runs = stats.get("runs", 0)
        clicks = stats.get("clicks", 0)
        ctr = round(clicks / runs, 4) if runs > 0 else 0.0
        result[name] = {"runs": runs, "clicks": clicks, "ctr": ctr}

    # Determine winner (min 10 runs per variant for statistical confidence)
    winner = None
    a_stats = result.get("A", {})
    b_stats = result.get("B", {})
    if a_stats.get("runs", 0) >= 10 and b_stats.get("runs", 0) >= 10:
        if b_stats["ctr"] > a_stats["ctr"] * 1.05:
            winner = "B"
        elif a_stats["ctr"] > b_stats["ctr"] * 1.05:
            winner = "A"

    return {
        "variants": result,
        "winner": winner,
        "total_assignments": len(data.get("assignments", {})),
    }


def get_variant_style(variant: str) -> str | None:
    """Return the system prompt modifier for variant B, or None for A."""
    if variant == "B":
        return VARIANT_B_STYLE
    return None
