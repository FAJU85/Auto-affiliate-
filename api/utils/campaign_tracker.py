import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CAMPAIGNS_FILE = DATA_DIR / "campaigns.json"


def _load() -> dict:
    try:
        return json.loads(CAMPAIGNS_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(CAMPAIGNS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(CAMPAIGNS_FILE)


def create_campaign(name: str, description: str = "") -> dict:
    data = _load()
    cid = uuid.uuid4().hex[:12]
    campaign = {
        "id": cid,
        "name": name,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "posts": [],
    }
    data[cid] = campaign
    _save(data)
    return campaign


def add_post_to_campaign(campaign_id: str, run: dict) -> bool:
    data = _load()
    if campaign_id not in data:
        return False
    data[campaign_id]["posts"].append({
        "timestamp": run.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "platform": run.get("platform", "unknown"),
        "clicks": int(run.get("clicks", 0)),
        "success": bool(run.get("success", False)),
    })
    _save(data)
    return True


def get_campaign(campaign_id: str) -> dict | None:
    return _load().get(campaign_id)


def list_campaigns() -> list[dict]:
    return list(_load().values())


def campaign_stats(campaign_id: str) -> dict | None:
    campaign = get_campaign(campaign_id)
    if campaign is None:
        return None
    posts = campaign.get("posts", [])
    successful = [p for p in posts if p.get("success")]
    total_clicks = sum(p.get("clicks", 0) for p in successful)
    return {
        "id": campaign_id,
        "name": campaign["name"],
        "total_posts": len(posts),
        "successful_posts": len(successful),
        "total_clicks": total_clicks,
        "avg_clicks": round(total_clicks / len(successful), 2) if successful else 0.0,
    }


def delete_campaign(campaign_id: str) -> bool:
    data = _load()
    if campaign_id not in data:
        return False
    del data[campaign_id]
    _save(data)
    return True
