import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LEVELS = ("info", "warning", "error", "success")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "notifications.json"


def _load() -> list[dict]:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return []


def _save(data: list[dict]) -> None:
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


def push(message: str, level: str = "info", category: str = "", data: dict | None = None) -> str:
    if level not in _LEVELS:
        raise ValueError(f"Unknown level {level!r}. Valid: {_LEVELS}")
    nid = str(uuid.uuid4())[:8]
    notifications = _load()
    notifications.append({
        "id": nid,
        "message": message,
        "level": level,
        "category": category,
        "data": data or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(notifications)
    return nid


def mark_read(nid: str) -> bool:
    notifications = _load()
    for n in notifications:
        if n["id"] == nid:
            n["read"] = True
            _save(notifications)
            return True
    return False


def mark_all_read() -> int:
    notifications = _load()
    count = 0
    for n in notifications:
        if not n["read"]:
            n["read"] = True
            count += 1
    _save(notifications)
    return count


def get_unread(level: str | None = None) -> list[dict]:
    notifications = _load()
    result = [n for n in notifications if not n["read"]]
    if level:
        result = [n for n in result if n["level"] == level]
    return sorted(result, key=lambda x: x["created_at"], reverse=True)


def get_all(limit: int = 50) -> list[dict]:
    notifications = _load()
    return sorted(notifications, key=lambda x: x["created_at"], reverse=True)[:limit]


def delete(nid: str) -> bool:
    notifications = _load()
    before = len(notifications)
    notifications = [n for n in notifications if n["id"] != nid]
    if len(notifications) < before:
        _save(notifications)
        return True
    return False


def notification_stats() -> dict:
    notifications = _load()
    unread = sum(1 for n in notifications if not n["read"])
    by_level: dict[str, int] = {}
    for n in notifications:
        by_level[n["level"]] = by_level.get(n["level"], 0) + 1
    return {
        "total": len(notifications),
        "unread": unread,
        "by_level": by_level,
    }
