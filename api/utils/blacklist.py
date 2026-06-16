"""Persistent product blacklist stored in /data/blacklist.json.

Allows blocking specific products (by name substring) or entire domains.
"""

import json
import os
from pathlib import Path

DATA_DIR       = Path(os.environ.get("DATA_DIR", "/data"))
BLACKLIST_FILE = DATA_DIR / "blacklist.json"

_EMPTY: dict = {"products": [], "domains": []}


def _load() -> dict:
    try:
        data = json.loads(BLACKLIST_FILE.read_text())
        return {
            "products": list(data.get("products", [])),
            "domains":  list(data.get("domains", [])),
        }
    except Exception:  # noqa: BLE001
        return {"products": [], "domains": []}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(BLACKLIST_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(BLACKLIST_FILE)


def add_product(name: str) -> None:
    """Add a lowercased product name substring to the blacklist (no duplicates)."""
    key = name.lower().strip()
    if not key:
        return
    data = _load()
    if key not in data["products"]:
        data["products"].append(key)
        _save(data)


def add_domain(domain: str) -> None:
    """Add a lowercased domain to the blacklist (no duplicates)."""
    key = domain.lower().strip()
    if not key:
        return
    data = _load()
    if key not in data["domains"]:
        data["domains"].append(key)
        _save(data)


def remove_product(name: str) -> bool:
    """Remove a product name substring. Returns True if it was present."""
    key = name.lower().strip()
    data = _load()
    if key in data["products"]:
        data["products"].remove(key)
        _save(data)
        return True
    return False


def remove_domain(domain: str) -> bool:
    """Remove a domain. Returns True if it was present."""
    key = domain.lower().strip()
    data = _load()
    if key in data["domains"]:
        data["domains"].remove(key)
        _save(data)
        return True
    return False


def is_blacklisted(product: dict) -> bool:
    """Return True if the product's name or URL matches any blacklist entry."""
    data = _load()
    name = (product.get("name") or "").lower()
    url  = (product.get("url") or product.get("siteUrl") or product.get("deeplink") or "").lower()

    for substring in data["products"]:
        if substring and substring in name:
            return True

    for domain in data["domains"]:
        if domain and domain in url:
            return True

    return False


def get_blacklist() -> dict:
    """Return the full blacklist as {"products": [...], "domains": [...]}."""
    return _load()
