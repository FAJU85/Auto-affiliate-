import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "link_tracker.json"


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


def register_link(original_url: str, product_id: str = "", platform: str = "") -> str:
    data = _load()
    # check if already registered
    for slug, entry in data.items():
        if entry["url"] == original_url and entry.get("platform", "") == platform.lower():
            return slug
    slug = str(uuid.uuid4())[:8]
    data[slug] = {
        "url": original_url,
        "product_id": product_id,
        "platform": platform.lower(),
        "clicks": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_clicked": None,
    }
    _save(data)
    return slug


def resolve(slug: str) -> str | None:
    return _load().get(slug, {}).get("url")


def record_click(slug: str) -> bool:
    data = _load()
    if slug not in data:
        return False
    data[slug]["clicks"] += 1
    data[slug]["last_clicked"] = datetime.now(timezone.utc).isoformat()
    _save(data)
    return True


def get_stats(slug: str) -> dict | None:
    entry = _load().get(slug)
    return dict(entry) if entry else None


def top_links(n: int = 10) -> list[dict]:
    data = _load()
    entries = [{"slug": s, **v} for s, v in data.items()]
    return sorted(entries, key=lambda x: x["clicks"], reverse=True)[:n]


def link_summary() -> dict:
    data = _load()
    total_clicks = sum(v["clicks"] for v in data.values())
    return {
        "total_links": len(data),
        "total_clicks": total_clicks,
        "top_slug": max(data, key=lambda s: data[s]["clicks"], default=None),
    }
