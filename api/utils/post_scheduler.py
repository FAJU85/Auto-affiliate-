import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "post_schedule.json"


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


def schedule_post(
    platform: str,
    content: str,
    scheduled_at: datetime,
    product_id: str = "",
) -> str:
    job_id = str(uuid.uuid4())[:8]
    jobs = _load()
    jobs.append({
        "id": job_id,
        "platform": platform.lower(),
        "content": content,
        "product_id": product_id,
        "scheduled_at": scheduled_at.isoformat(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(jobs)
    return job_id


def get_due(now: datetime | None = None) -> list[dict]:
    if now is None:
        now = datetime.now(timezone.utc)
    return [
        j for j in _load()
        if j["status"] == "pending"
        and datetime.fromisoformat(j["scheduled_at"]) <= now
    ]


def mark_done(job_id: str) -> bool:
    jobs = _load()
    for j in jobs:
        if j["id"] == job_id:
            j["status"] = "done"
            _save(jobs)
            return True
    return False


def mark_failed(job_id: str, reason: str = "") -> bool:
    jobs = _load()
    for j in jobs:
        if j["id"] == job_id:
            j["status"] = "failed"
            j["error"] = reason
            _save(jobs)
            return True
    return False


def cancel(job_id: str) -> bool:
    jobs = _load()
    for j in jobs:
        if j["id"] == job_id and j["status"] == "pending":
            j["status"] = "cancelled"
            _save(jobs)
            return True
    return False


def list_jobs(status: str | None = None) -> list[dict]:
    jobs = _load()
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    return sorted(jobs, key=lambda x: x["scheduled_at"])


def queue_stats() -> dict:
    jobs = _load()
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    return {
        "total": len(jobs),
        "pending": counts.get("pending", 0),
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "cancelled": counts.get("cancelled", 0),
    }
