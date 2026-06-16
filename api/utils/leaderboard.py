import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_METRICS = ("clicks", "revenue", "conversions", "score")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "leaderboard.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"entries": {}}


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


def _default_entry(product_id: str, title: str) -> dict:
    return {
        "product_id": product_id,
        "title": title,
        "clicks": 0,
        "revenue": 0.0,
        "conversions": 0,
        "score": 0.0,
        "updated_at": _now_iso(),
    }


def record(product_id: str, title: str, clicks: int = 0, revenue: float = 0.0, conversions: int = 0) -> None:
    data = _load()
    if product_id not in data["entries"]:
        data["entries"][product_id] = _default_entry(product_id, title)
    entry = data["entries"][product_id]
    entry["title"] = title
    entry["clicks"] += clicks
    entry["revenue"] = round(entry["revenue"] + revenue, 4)
    entry["conversions"] += conversions
    entry["score"] = round(
        entry["clicks"] * 0.3 + entry["revenue"] * 0.5 + entry["conversions"] * 100 * 0.2, 4
    )
    entry["updated_at"] = _now_iso()
    _save(data)


def get_entry(product_id: str) -> dict | None:
    return _load()["entries"].get(product_id)


def rank(metric: str = "score", top_n: int | None = None) -> list[dict]:
    if metric not in _METRICS:
        raise ValueError(f"Metric must be one of {_METRICS}")
    entries = list(_load()["entries"].values())
    ranked = sorted(entries, key=lambda x: x.get(metric, 0), reverse=True)
    if top_n is not None:
        ranked = ranked[:top_n]
    total = len(_load()["entries"])
    for i, entry in enumerate(ranked):
        entry = dict(entry)
        entry["rank"] = i + 1
        entry["percentile"] = round((1 - i / total) * 100, 1) if total > 0 else 100.0
        ranked[i] = entry
    return ranked


def podium(metric: str = "score") -> list[dict]:
    return rank(metric=metric, top_n=3)


def reset_entry(product_id: str) -> bool:
    data = _load()
    if product_id not in data["entries"]:
        return False
    title = data["entries"][product_id]["title"]
    data["entries"][product_id] = _default_entry(product_id, title)
    _save(data)
    return True


def leaderboard_stats() -> dict:
    entries = list(_load()["entries"].values())
    if not entries:
        return {"total": 0, "total_clicks": 0, "total_revenue": 0.0, "total_conversions": 0}
    return {
        "total": len(entries),
        "total_clicks": sum(e["clicks"] for e in entries),
        "total_revenue": round(sum(e["revenue"] for e in entries), 4),
        "total_conversions": sum(e["conversions"] for e in entries),
    }
