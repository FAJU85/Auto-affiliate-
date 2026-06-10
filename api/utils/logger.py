"""In-memory log ring buffer (last 200 entries) + stdout passthrough.

Each entry is a dict: {ts, level, msg} — matching what the dashboard expects
for filterLogs() (filters on l.level) and error counting.
"""

import sys
from collections import deque
from datetime import datetime, timezone

_RING: deque = deque(maxlen=200)


def _emit(level: str, msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    entry = {"ts": ts, "level": level.lower(), "msg": str(msg)}
    _RING.append(entry)
    line = f"[{ts}] [{level}] {msg}"
    stream = sys.stderr if level == "ERROR" else sys.stdout
    print(line, file=stream, flush=True)


def info(msg: str) -> None:
    _emit("INFO", str(msg))


def warn(msg: str) -> None:
    _emit("WARN", str(msg))


def error(msg: str) -> None:
    _emit("ERROR", str(msg))


def get_recent_logs(n: int = 100) -> list[dict]:
    items = list(_RING)
    return items[-n:]
