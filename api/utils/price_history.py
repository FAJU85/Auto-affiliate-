import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "price_history.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", dir=p.parent, delete=False, suffix=".tmp")
    try:
        json.dump(data, tmp)
        tmp.close()
        os.replace(tmp.name, p)
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise


def record_price(product_id: str, price: float) -> None:
    data = _load()
    entry = {"price": price, "ts": datetime.now(timezone.utc).isoformat()}
    data.setdefault(product_id, []).append(entry)
    _save(data)


def get_history(product_id: str) -> list[dict]:
    return _load().get(product_id, [])


def latest_price(product_id: str) -> float | None:
    history = get_history(product_id)
    return history[-1]["price"] if history else None


def price_change(product_id: str) -> dict | None:
    history = get_history(product_id)
    if len(history) < 2:
        return None
    old = history[-2]["price"]
    new = history[-1]["price"]
    delta = new - old
    pct = (delta / old * 100) if old else 0.0
    return {
        "old": old,
        "new": new,
        "delta": round(delta, 4),
        "pct": round(pct, 2),
        "direction": "drop" if delta < 0 else ("rise" if delta > 0 else "unchanged"),
    }


def price_summary(product_id: str) -> dict:
    history = get_history(product_id)
    if not history:
        return {"count": 0, "min": None, "max": None, "latest": None}
    prices = [e["price"] for e in history]
    return {
        "count": len(prices),
        "min": min(prices),
        "max": max(prices),
        "latest": prices[-1],
    }


def all_drops(min_pct: float = 5.0) -> list[dict]:
    data = _load()
    drops = []
    for pid in data:
        ch = price_change(pid)
        if ch and ch["direction"] == "drop" and abs(ch["pct"]) >= min_pct:
            drops.append({"product_id": pid, **ch})
    return sorted(drops, key=lambda x: x["pct"])
