import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "content_freshness.json"


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


def _key(product_id: str, platform: str) -> str:
    return f"{product_id}::{platform.lower()}"


def record_post(product_id: str, platform: str) -> None:
    data = _load()
    data[_key(product_id, platform)] = datetime.now(timezone.utc).isoformat()
    _save(data)


def last_posted(product_id: str, platform: str) -> datetime | None:
    data = _load()
    ts = data.get(_key(product_id, platform))
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def is_fresh(product_id: str, platform: str, min_hours: int = 24) -> bool:
    lp = last_posted(product_id, platform)
    if lp is None:
        return True
    age = datetime.now(timezone.utc) - lp
    return age >= timedelta(hours=min_hours)


def freshness_report(min_hours: int = 24) -> dict:
    data = _load()
    now = datetime.now(timezone.utc)
    stale, fresh, never = [], [], []
    for key, ts in data.items():
        product_id, platform = key.split("::", 1)
        try:
            posted_at = datetime.fromisoformat(ts)
            age_h = (now - posted_at).total_seconds() / 3600
            entry = {"product_id": product_id, "platform": platform, "hours_ago": round(age_h, 1)}
            if age_h >= min_hours:
                stale.append(entry)
            else:
                fresh.append(entry)
        except Exception:
            never.append({"product_id": product_id, "platform": platform})
    return {
        "total_tracked": len(data),
        "stale_count": len(stale),
        "fresh_count": len(fresh),
        "stale": sorted(stale, key=lambda x: x["hours_ago"], reverse=True),
        "fresh": sorted(fresh, key=lambda x: x["hours_ago"], reverse=True),
    }


def clear_product(product_id: str) -> int:
    data = _load()
    prefix = f"{product_id}::"
    keys = [k for k in data if k.startswith(prefix)]
    for k in keys:
        del data[k]
    _save(data)
    return len(keys)
