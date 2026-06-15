"""Price history tracker and drop-alert detector.

Stores the last seen price for each product (keyed by ASIN or URL).
When a product is re-fetched, compare against stored price.
A drop ≥ DROP_THRESHOLD (20%) triggers a price-drop alert.

Data file: DATA_DIR/price_history.json
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DROP_THRESHOLD = 0.20   # 20% price drop required to trigger alert
MAX_AGE_DAYS = 30       # only compare against prices seen within 30 days


def _file() -> Path:
    return Path(os.environ.get("DATA_DIR", str(DATA_DIR))) / "price_history.json"


def _load() -> dict:
    f = _file()
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2))


def _product_key(product: dict) -> str | None:
    """Stable key for a product — ASIN preferred, then URL, then name."""
    asin = product.get("asin")
    if asin:
        return f"asin:{asin}"
    url = product.get("deeplink") or product.get("siteUrl")
    if url:
        return f"url:{url}"
    name = product.get("name")
    if name:
        return f"name:{name.lower().strip()}"
    return None


def record_price(product: dict) -> None:
    """Store the current price for a product."""
    key = _product_key(product)
    price = product.get("price")
    if not key or price is None or float(price) <= 0:
        return

    data = _load()
    data[key] = {
        "price": float(price),
        "name": product.get("name", ""),
        "timestamp": time.time(),
        "source": product.get("source", ""),
    }
    _save(data)


def check_price_drop(product: dict) -> dict | None:
    """Compare product's current price against history.

    Returns a dict with drop info if a significant drop is detected,
    else None.

    Return shape:
      {"drop_pct": 0.25, "old_price": 100.0, "new_price": 75.0, "name": "...", "key": "..."}
    """
    key = _product_key(product)
    current_price = product.get("price")
    if not key or current_price is None or float(current_price) <= 0:
        return None

    current_price = float(current_price)
    data = _load()
    entry = data.get(key)
    if not entry:
        return None

    # Ignore stale records
    age_days = (time.time() - entry.get("timestamp", 0)) / 86_400
    if age_days > MAX_AGE_DAYS:
        return None

    old_price = float(entry.get("price", 0))
    if old_price <= 0:
        return None

    drop_pct = (old_price - current_price) / old_price
    if drop_pct >= DROP_THRESHOLD:
        return {
            "drop_pct": round(drop_pct, 4),
            "old_price": old_price,
            "new_price": current_price,
            "name": product.get("name", entry.get("name", "")),
            "key": key,
        }
    return None


def get_price_history(product: dict) -> dict | None:
    """Return the stored price record for a product, or None."""
    key = _product_key(product)
    if not key:
        return None
    return _load().get(key)


def clear_stale(max_age_days: int = MAX_AGE_DAYS) -> int:
    """Remove entries older than max_age_days. Returns count removed."""
    data = _load()
    cutoff = time.time() - max_age_days * 86_400
    keep = {k: v for k, v in data.items() if v.get("timestamp", 0) >= cutoff}
    removed = len(data) - len(keep)
    if removed:
        _save(keep)
    return removed
