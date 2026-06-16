import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

_STALE_HOURS = 24
_DRIFT_THRESHOLD = 0.3  # 30% product count change = drift


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "feed_health.json"


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_fetch(feed: str, product_count: int, success: bool = True, error: str | None = None) -> None:
    data = _load()
    if feed not in data:
        data[feed] = {"fetches": [], "baseline_count": None}
    entry = {
        "product_count": product_count,
        "success": success,
        "error": error,
        "ts": _now_iso(),
    }
    data[feed]["fetches"].append(entry)
    data[feed]["fetches"] = data[feed]["fetches"][-50:]
    if success and data[feed]["baseline_count"] is None:
        data[feed]["baseline_count"] = product_count
    _save(data)


def is_stale(feed: str, stale_hours: int = _STALE_HOURS) -> bool:
    data = _load()
    fetches = data.get(feed, {}).get("fetches", [])
    if not fetches:
        return True
    last_success = next((f for f in reversed(fetches) if f.get("success")), None)
    if not last_success:
        return True
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=stale_hours)).isoformat()
    return last_success["ts"] < cutoff


def has_drift(feed: str, threshold: float = _DRIFT_THRESHOLD) -> bool:
    data = _load()
    entry = data.get(feed, {})
    baseline = entry.get("baseline_count")
    fetches = entry.get("fetches", [])
    if baseline is None or not fetches:
        return False
    last_success = next((f for f in reversed(fetches) if f.get("success")), None)
    if not last_success or last_success["product_count"] == 0:
        return False
    change = abs(last_success["product_count"] - baseline) / max(baseline, 1)
    return change >= threshold


def get_status(feed: str) -> dict:
    data = _load()
    entry = data.get(feed, {})
    fetches = entry.get("fetches", [])
    last_success = next((f for f in reversed(fetches) if f.get("success")), None)
    last_fetch = fetches[-1] if fetches else None
    total = len(fetches)
    failures = sum(1 for f in fetches if not f.get("success"))
    return {
        "feed": feed,
        "last_fetch_ts": last_fetch["ts"] if last_fetch else None,
        "last_success_ts": last_success["ts"] if last_success else None,
        "last_product_count": last_success["product_count"] if last_success else None,
        "baseline_count": entry.get("baseline_count"),
        "total_fetches": total,
        "failures": failures,
        "is_stale": is_stale(feed),
        "has_drift": has_drift(feed),
    }


def feed_health_summary() -> list[dict]:
    data = _load()
    return sorted([get_status(f) for f in data], key=lambda x: x["feed"])
