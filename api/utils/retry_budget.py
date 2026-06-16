import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "retry_budget.json"


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


def _default_entry(max_retries: int) -> dict:
    return {
        "count": 0,
        "max_retries": max_retries,
        "exhausted": False,
        "last_retry": None,
        "created_at": _now_iso(),
    }


def can_retry(resource: str, max_retries: int = 3) -> bool:
    data = _load()
    entry = data.get(resource)
    if entry is None:
        return True
    return not entry.get("exhausted", False) and entry.get("count", 0) < entry.get("max_retries", max_retries)


def consume(resource: str, max_retries: int = 3) -> bool:
    data = _load()
    if resource not in data:
        data[resource] = _default_entry(max_retries)
    entry = data[resource]
    if entry.get("exhausted") or entry["count"] >= entry["max_retries"]:
        entry["exhausted"] = True
        _save(data)
        return False
    entry["count"] += 1
    entry["last_retry"] = _now_iso()
    if entry["count"] >= entry["max_retries"]:
        entry["exhausted"] = True
    _save(data)
    return True


def reset(resource: str) -> bool:
    data = _load()
    if resource not in data:
        return False
    max_r = data[resource].get("max_retries", 3)
    data[resource] = _default_entry(max_r)
    _save(data)
    return True


def get_budget(resource: str) -> dict | None:
    return _load().get(resource)


def remaining(resource: str, max_retries: int = 3) -> int:
    entry = get_budget(resource)
    if entry is None:
        return max_retries
    if entry.get("exhausted"):
        return 0
    return max(0, entry.get("max_retries", max_retries) - entry.get("count", 0))


def budget_summary() -> list[dict]:
    data = _load()
    result = []
    for res, entry in data.items():
        result.append({
            "resource": res,
            "count": entry.get("count", 0),
            "max_retries": entry.get("max_retries", 3),
            "remaining": max(0, entry.get("max_retries", 3) - entry.get("count", 0)),
            "exhausted": entry.get("exhausted", False),
        })
    return sorted(result, key=lambda x: x["resource"])
