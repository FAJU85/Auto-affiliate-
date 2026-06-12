"""Request/Response Snapshot Logger.

Every API response shape is captured to logs/snapshots/<endpoint>.json.
The pattern_detector script reads these to find drift vs. the learned shapes
in .qa_memory.json.

Only active when SNAPSHOT_DIR env var is set (or auto-enabled in test mode).
"""

import json
import os
import re
import time
from pathlib import Path


def _snapshot_dir() -> Path | None:
    d = os.environ.get("SNAPSHOT_DIR")
    if d:
        return Path(d)
    return None


def _safe_name(path: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", path.strip("/")) or "root"


def record_response(endpoint: str, body: dict) -> None:
    """Append a timestamped snapshot of `body` for `endpoint`."""
    d = _snapshot_dir()
    if d is None:
        return
    d.mkdir(parents=True, exist_ok=True)
    fname = d / f"{_safe_name(endpoint)}.jsonl"
    entry = {"ts": time.time(), "endpoint": endpoint, "keys": sorted(body.keys())}
    with open(fname, "a") as f:
        f.write(json.dumps(entry) + "\n")
