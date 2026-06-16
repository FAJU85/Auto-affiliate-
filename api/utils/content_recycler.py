import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

_MIN_RECYCLE_DAYS = 14  # don't re-post within 14 days


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "content_recycler.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"posts": {}}


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


def record_post(content_id: str, platform: str, content: str, clicks: int = 0) -> None:
    data = _load()
    key = f"{content_id}:{platform}"
    if key not in data["posts"]:
        data["posts"][key] = {
            "content_id": content_id,
            "platform": platform,
            "content": content,
            "history": [],
        }
    data["posts"][key]["history"].append({
        "ts": _now_iso(),
        "clicks": clicks,
    })
    data["posts"][key]["history"] = data["posts"][key]["history"][-20:]
    _save(data)


def can_recycle(content_id: str, platform: str, min_days: int = _MIN_RECYCLE_DAYS) -> bool:
    data = _load()
    key = f"{content_id}:{platform}"
    entry = data["posts"].get(key)
    if not entry or not entry["history"]:
        return True
    if min_days == 0:
        return True
    last_ts = entry["history"][-1]["ts"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=min_days)).isoformat()
    return last_ts < cutoff


def freshness_score(content_id: str, platform: str, min_days: int = _MIN_RECYCLE_DAYS) -> float:
    data = _load()
    key = f"{content_id}:{platform}"
    entry = data["posts"].get(key)
    if not entry or not entry["history"]:
        return 1.0
    last_ts = datetime.fromisoformat(entry["history"][-1]["ts"])
    age_days = (datetime.now(timezone.utc) - last_ts.replace(tzinfo=timezone.utc)).days
    if min_days == 0:
        return 1.0
    score = min(1.0, age_days / min_days)
    return round(score, 3)


def get_recyclable(platform: str | None = None, min_days: int = _MIN_RECYCLE_DAYS) -> list[dict]:
    data = _load()
    result = []
    for key, entry in data["posts"].items():
        if platform and entry["platform"] != platform:
            continue
        if can_recycle(entry["content_id"], entry["platform"], min_days):
            score = freshness_score(entry["content_id"], entry["platform"], min_days)
            total_clicks = sum(h["clicks"] for h in entry["history"])
            result.append({
                "content_id": entry["content_id"],
                "platform": entry["platform"],
                "content": entry["content"],
                "times_posted": len(entry["history"]),
                "total_clicks": total_clicks,
                "freshness_score": score,
            })
    return sorted(result, key=lambda x: x["total_clicks"], reverse=True)


def recycler_stats() -> dict:
    data = _load()
    entries = list(data["posts"].values())
    return {
        "total_tracked": len(entries),
        "recyclable_now": len([e for e in entries if can_recycle(e["content_id"], e["platform"])]),
        "total_posts": sum(len(e["history"]) for e in entries),
    }
