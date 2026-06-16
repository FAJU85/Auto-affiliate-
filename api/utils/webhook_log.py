import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "webhook_log.json"


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


def _fingerprint(event_type: str, payload: dict) -> str:
    raw = json.dumps({"type": event_type, "payload": payload}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def log_event(
    event_type: str,
    payload: dict,
    source: str = "",
    dedupe: bool = True,
    dedupe_window_seconds: int = 300,
) -> dict:
    fp = _fingerprint(event_type, payload)
    events = _load()

    if dedupe:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=dedupe_window_seconds)
        for e in events:
            if e.get("fingerprint") == fp:
                try:
                    ts = datetime.fromisoformat(e["received_at"])
                    if ts >= cutoff:
                        return {**e, "duplicate": True}
                except Exception:
                    pass

    entry = {
        "id": f"{event_type}:{fp}:{len(events)}",
        "event_type": event_type,
        "source": source,
        "payload": payload,
        "fingerprint": fp,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "replayed": False,
    }
    events.append(entry)
    _save(events)
    return {**entry, "duplicate": False}


def get_events(event_type: str | None = None, limit: int = 100) -> list[dict]:
    events = _load()
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]
    return sorted(events, key=lambda x: x["received_at"], reverse=True)[:limit]


def mark_replayed(event_id: str) -> bool:
    events = _load()
    for e in events:
        if e["id"] == event_id:
            e["replayed"] = True
            _save(events)
            return True
    return False


def event_stats() -> dict:
    events = _load()
    by_type: dict[str, int] = {}
    for e in events:
        t = e.get("event_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return {
        "total": len(events),
        "by_type": by_type,
        "replayed": sum(1 for e in events if e.get("replayed")),
    }
