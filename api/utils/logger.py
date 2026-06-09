"""In-memory log ring buffer (last 200 entries) + stdout passthrough."""

import sys
from collections import deque
from datetime import datetime, timezone

_RING: deque = deque(maxlen=200)


def _emit(level: str, msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] [{level}] {msg}"
    _RING.append(line)
    stream = sys.stderr if level == "ERROR" else sys.stdout
    print(line, file=stream, flush=True)


def info(msg: str) -> None:
    _emit("INFO", str(msg))


def warn(msg: str) -> None:
    _emit("WARN", str(msg))


def error(msg: str) -> None:
    _emit("ERROR", str(msg))


def get_recent_logs(n: int = 100) -> list[str]:
    items = list(_RING)
    return items[-n:]
