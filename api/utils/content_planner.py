import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_VALID_STATUSES = ("draft", "scheduled", "published", "cancelled")
_PLATFORMS = ("twitter", "instagram", "bluesky", "mastodon", "facebook", "threads", "tumblr")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "content_plan.json"


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


def add_item(
    title: str,
    theme: str,
    platforms: list[str],
    scheduled_for: str | None = None,
    notes: str = "",
) -> str:
    item_id = str(uuid.uuid4())[:8]
    data = _load()
    data["items"][item_id] = {
        "id": item_id,
        "title": title,
        "theme": theme,
        "platforms": platforms,
        "scheduled_for": scheduled_for,
        "notes": notes,
        "status": "draft",
        "created_at": _now_iso(),
        "published_at": None,
    }
    _save(data)
    return item_id


def get_item(item_id: str) -> dict | None:
    return _load()["items"].get(item_id)


def update_status(item_id: str, status: str) -> bool:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Status must be one of {_VALID_STATUSES}")
    data = _load()
    if item_id not in data["items"]:
        return False
    data["items"][item_id]["status"] = status
    if status == "published":
        data["items"][item_id]["published_at"] = _now_iso()
    _save(data)
    return True


def get_by_status(status: str) -> list[dict]:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Status must be one of {_VALID_STATUSES}")
    items = _load()["items"].values()
    return sorted([i for i in items if i["status"] == status], key=lambda x: x.get("scheduled_for") or x["created_at"])


def get_by_theme(theme: str) -> list[dict]:
    items = _load()["items"].values()
    return [i for i in items if i["theme"].lower() == theme.lower()]


def get_by_platform(platform: str) -> list[dict]:
    items = _load()["items"].values()
    return [i for i in items if platform.lower() in [p.lower() for p in i.get("platforms", [])]]


def delete_item(item_id: str) -> bool:
    data = _load()
    if item_id not in data["items"]:
        return False
    del data["items"][item_id]
    _save(data)
    return True


def planner_stats() -> dict:
    items = list(_load()["items"].values())
    stats: dict = {"total": len(items)}
    for s in _VALID_STATUSES:
        stats[s] = sum(1 for i in items if i["status"] == s)
    themes: dict = {}
    for i in items:
        themes[i["theme"]] = themes.get(i["theme"], 0) + 1
    stats["themes"] = themes
    return stats
