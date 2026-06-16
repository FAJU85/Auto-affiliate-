import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_EVENT_TYPES = ("start", "post", "error", "skip", "end", "info")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "session_log.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"sessions": {}}


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


def start_session(meta: dict | None = None) -> str:
    session_id = str(uuid.uuid4())[:8]
    data = _load()
    data["sessions"][session_id] = {
        "id": session_id,
        "started_at": _now_iso(),
        "ended_at": None,
        "meta": meta or {},
        "events": [],
    }
    _save(data)
    return session_id


def log_event(session_id: str, event_type: str, message: str, payload: dict | None = None) -> bool:
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"Unknown event type {event_type!r}. Valid: {_EVENT_TYPES}")
    data = _load()
    if session_id not in data["sessions"]:
        return False
    data["sessions"][session_id]["events"].append({
        "type": event_type,
        "message": message,
        "payload": payload or {},
        "ts": _now_iso(),
    })
    _save(data)
    return True


def end_session(session_id: str) -> bool:
    data = _load()
    if session_id not in data["sessions"]:
        return False
    data["sessions"][session_id]["ended_at"] = _now_iso()
    _save(data)
    return True


def get_session(session_id: str) -> dict | None:
    return _load()["sessions"].get(session_id)


def get_events(session_id: str, event_type: str | None = None) -> list[dict]:
    session = get_session(session_id)
    if not session:
        return []
    events = session.get("events", [])
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    return events


def session_summary(session_id: str) -> dict | None:
    session = get_session(session_id)
    if not session:
        return None
    events = session.get("events", [])
    counts: dict = {t: 0 for t in _EVENT_TYPES}
    for e in events:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    return {
        "id": session_id,
        "started_at": session["started_at"],
        "ended_at": session["ended_at"],
        "event_count": len(events),
        **counts,
    }


def list_sessions() -> list[dict]:
    data = _load()
    return sorted(
        [{"id": sid, "started_at": s["started_at"], "ended_at": s["ended_at"], "event_count": len(s["events"])}
         for sid, s in data["sessions"].items()],
        key=lambda x: x["started_at"],
        reverse=True,
    )
