import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "rate_limits.json"


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def record_hit(platform: str, limit: int, window_seconds: int = 3600) -> dict:
    data = _load()
    now = _now()
    window_start = (now - timedelta(seconds=window_seconds)).isoformat()

    if platform not in data:
        data[platform] = {"hits": [], "limit": limit, "window_seconds": window_seconds}

    entry = data[platform]
    entry["limit"] = limit
    entry["window_seconds"] = window_seconds
    entry["hits"] = [h for h in entry.get("hits", []) if h >= window_start]
    entry["hits"].append(now.isoformat())

    _save(data)
    return _status(platform, entry, now)


def is_limited(platform: str) -> bool:
    data = _load()
    entry = data.get(platform)
    if not entry:
        return False
    now = _now()
    window_start = (now - timedelta(seconds=entry.get("window_seconds", 3600))).isoformat()
    active_hits = [h for h in entry.get("hits", []) if h >= window_start]
    return len(active_hits) >= entry.get("limit", 0)


def reset_platform(platform: str) -> bool:
    data = _load()
    if platform not in data:
        return False
    data[platform]["hits"] = []
    _save(data)
    return True


def _status(platform: str, entry: dict, now: datetime) -> dict:
    window_seconds = entry.get("window_seconds", 3600)
    window_start = (now - timedelta(seconds=window_seconds)).isoformat()
    active_hits = [h for h in entry.get("hits", []) if h >= window_start]
    limit = entry.get("limit", 0)
    remaining = max(0, limit - len(active_hits))
    reset_at = None
    if active_hits:
        oldest = min(active_hits)
        reset_at = (datetime.fromisoformat(oldest) + timedelta(seconds=window_seconds)).isoformat()
    return {
        "platform": platform,
        "hits_in_window": len(active_hits),
        "limit": limit,
        "remaining": remaining,
        "is_limited": remaining == 0,
        "reset_at": reset_at,
        "window_seconds": window_seconds,
    }


def get_status(platform: str) -> dict | None:
    data = _load()
    entry = data.get(platform)
    if entry is None:
        return None
    return _status(platform, entry, _now())


def rate_limit_summary() -> list[dict]:
    data = _load()
    now = _now()
    return sorted(
        [_status(p, e, now) for p, e in data.items()],
        key=lambda x: x["platform"],
    )
