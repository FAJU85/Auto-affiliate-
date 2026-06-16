import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "watchlist.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"items": {}}


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def watch(product_id: str, title: str, url: str, target_price: float | None = None) -> bool:
    data = _load()
    if product_id in data["items"]:
        return False
    data["items"][product_id] = {
        "product_id": product_id,
        "title": title,
        "url": url,
        "target_price": target_price,
        "last_price": None,
        "price_history": [],
        "alerts": [],
        "added_at": _now_iso(),
        "active": True,
    }
    _save(data)
    return True


def unwatch(product_id: str) -> bool:
    data = _load()
    if product_id not in data["items"]:
        return False
    del data["items"][product_id]
    _save(data)
    return True


def get_item(product_id: str) -> dict | None:
    return _load()["items"].get(product_id)


def update_price(product_id: str, price: float) -> dict | None:
    data = _load()
    if product_id not in data["items"]:
        return None
    item = data["items"][product_id]
    prev = item.get("last_price")
    item["price_history"].append({"price": price, "ts": _now_iso()})
    item["price_history"] = item["price_history"][-50:]
    item["last_price"] = price
    alert = None
    if prev is not None and price < prev:
        drop_pct = round((prev - price) / prev * 100, 1)
        alert = {"type": "price_drop", "from": prev, "to": price, "drop_pct": drop_pct, "ts": _now_iso()}
        item["alerts"].append(alert)
    elif item.get("target_price") is not None and price <= item["target_price"] and (prev is None or prev > item["target_price"]):
        alert = {"type": "target_reached", "target": item["target_price"], "price": price, "ts": _now_iso()}
        item["alerts"].append(alert)
    item["alerts"] = item["alerts"][-20:]
    _save(data)
    return alert


def get_alerts(product_id: str) -> list[dict]:
    item = get_item(product_id)
    return item.get("alerts", []) if item else []


def list_watched(active_only: bool = True) -> list[dict]:
    items = _load()["items"].values()
    if active_only:
        items = [i for i in items if i.get("active", True)]
    return sorted(items, key=lambda x: x["added_at"], reverse=True)


def watchlist_stats() -> dict:
    items = list(_load()["items"].values())
    with_target = sum(1 for i in items if i.get("target_price") is not None)
    with_alerts = sum(1 for i in items if i.get("alerts"))
    return {
        "total": len(items),
        "with_target_price": with_target,
        "with_alerts": with_alerts,
    }
