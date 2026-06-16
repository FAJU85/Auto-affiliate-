import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_VALID_STATUSES = ("pending", "sent", "failed", "cancelled")
_VALID_PRIORITIES = (1, 2, 3)  # 1=high, 2=normal, 3=low


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "post_queue.json"


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


def enqueue(platform: str, content: str, priority: int = 2, scheduled_at: str | None = None) -> str:
    if priority not in _VALID_PRIORITIES:
        raise ValueError(f"Priority must be one of {_VALID_PRIORITIES}")
    item_id = str(uuid.uuid4())[:8]
    data = _load()
    data["items"][item_id] = {
        "id": item_id,
        "platform": platform,
        "content": content,
        "priority": priority,
        "status": "pending",
        "scheduled_at": scheduled_at,
        "created_at": _now_iso(),
        "sent_at": None,
        "error": None,
    }
    _save(data)
    return item_id


def get_item(item_id: str) -> dict | None:
    return _load()["items"].get(item_id)


def update_status(item_id: str, status: str, error: str | None = None) -> bool:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Status must be one of {_VALID_STATUSES}")
    data = _load()
    if item_id not in data["items"]:
        return False
    data["items"][item_id]["status"] = status
    data["items"][item_id]["error"] = error
    if status == "sent":
        data["items"][item_id]["sent_at"] = _now_iso()
    _save(data)
    return True


def get_pending(platform: str | None = None) -> list[dict]:
    items = _load()["items"].values()
    pending = [i for i in items if i["status"] == "pending"]
    if platform:
        pending = [i for i in pending if i["platform"] == platform]
    return sorted(pending, key=lambda x: (x["priority"], x["created_at"]))


def cancel(item_id: str) -> bool:
    return update_status(item_id, "cancelled")


def queue_stats() -> dict:
    items = list(_load()["items"].values())
    stats: dict = {"total": len(items)}
    for s in _VALID_STATUSES:
        stats[s] = sum(1 for i in items if i["status"] == s)
    return stats
