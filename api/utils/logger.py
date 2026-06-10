"""In-memory log ring buffer (last 500 entries) + stdout passthrough.

Each entry: {ts, level, msg, component}
  component — optional tag: pipeline, bluesky, mastodon, x, threads, tumblr,
              oauth, scheduler, sovrn, ai, system
"""

import sys
from collections import deque
from datetime import datetime, timezone

_RING: deque = deque(maxlen=500)


def _emit(level: str, msg: str, component: str = "system") -> None:
    ts = datetime.now(timezone.utc).isoformat()
    entry = {"ts": ts, "level": level.lower(), "msg": str(msg), "component": component}
    _RING.append(entry)
    line = f"[{ts}] [{level}] [{component}] {msg}"
    stream = sys.stderr if level == "ERROR" else sys.stdout
    print(line, file=stream, flush=True)


def info(msg: str, component: str = "system") -> None:
    _emit("INFO", str(msg), component)


def warn(msg: str, component: str = "system") -> None:
    _emit("WARN", str(msg), component)


def error(msg: str, component: str = "system") -> None:
    _emit("ERROR", str(msg), component)


def get_recent_logs(n: int = 200) -> list[dict]:
    items = list(_RING)
    return items[-n:]


def clear_logs() -> int:
    n = len(_RING)
    _RING.clear()
    return n


def error_summary() -> dict:
    """Count errors/warnings by component for the health panel."""
    items = list(_RING)
    summary: dict = {}
    total_errors = 0
    total_warns = 0
    for e in items:
        lvl = e.get("level", "")
        comp = e.get("component", "system")
        if lvl == "error":
            total_errors += 1
            summary.setdefault(comp, {"errors": 0, "warns": 0})["errors"] += 1
        elif lvl == "warn":
            total_warns += 1
            summary.setdefault(comp, {"errors": 0, "warns": 0})["warns"] += 1
    return {
        "totalErrors": total_errors,
        "totalWarns": total_warns,
        "byComponent": summary,
        "lastError": next((e for e in reversed(items) if e.get("level") == "error"), None),
    }
