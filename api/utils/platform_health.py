import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

_PLATFORMS = ("twitter", "instagram", "bluesky", "mastodon", "facebook", "threads", "tumblr")
_DEGRADED_THRESHOLD = 0.5   # error rate above this = degraded
_WINDOW_HOURS = 24


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "platform_health.json"


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


def record(platform: str, success: bool, error: str | None = None) -> None:
    data = _load()
    if platform not in data:
        data[platform] = {"events": [], "paused": False}
    data[platform]["events"].append({
        "success": success,
        "error": error,
        "ts": _now_iso(),
    })
    # keep only last 100 events
    data[platform]["events"] = data[platform]["events"][-100:]
    _save(data)


def _recent_events(platform: str, data: dict, hours: int = _WINDOW_HOURS) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return [e for e in data.get(platform, {}).get("events", []) if e["ts"] >= cutoff]


def error_rate(platform: str, hours: int = _WINDOW_HOURS) -> float | None:
    data = _load()
    events = _recent_events(platform, data, hours)
    if not events:
        return None
    failures = sum(1 for e in events if not e["success"])
    return round(failures / len(events), 4)


def is_healthy(platform: str, hours: int = _WINDOW_HOURS) -> bool:
    data = _load()
    if data.get(platform, {}).get("paused"):
        return False
    rate = error_rate(platform, hours)
    if rate is None:
        return True
    return rate < _DEGRADED_THRESHOLD


def pause_platform(platform: str) -> None:
    data = _load()
    if platform not in data:
        data[platform] = {"events": [], "paused": True}
    else:
        data[platform]["paused"] = True
    _save(data)


def resume_platform(platform: str) -> bool:
    data = _load()
    if platform not in data:
        return False
    data[platform]["paused"] = False
    _save(data)
    return True


def get_status(platform: str) -> dict:
    data = _load()
    events = _recent_events(platform, data)
    total = len(events)
    failures = sum(1 for e in events if not e["success"])
    rate = round(failures / total, 4) if total else None
    paused = data.get(platform, {}).get("paused", False)
    healthy = not paused and (rate is None or rate < _DEGRADED_THRESHOLD)
    return {
        "platform": platform,
        "paused": paused,
        "healthy": healthy,
        "error_rate": rate,
        "events_in_window": total,
        "failures_in_window": failures,
    }


def health_summary() -> list[dict]:
    data = _load()
    platforms = set(data.keys()) | set(_PLATFORMS)
    return sorted([get_status(p) for p in platforms], key=lambda x: x["platform"])
