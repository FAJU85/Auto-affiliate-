import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
LOG_FILE = DATA_DIR / "activity_log.jsonl"
MAX_LINES = 5000


def _load_lines() -> list[str]:
    try:
        return LOG_FILE.read_text().splitlines()
    except Exception:  # noqa: BLE001
        return []


def log_request(
    endpoint: str,
    method: str,
    status_code: int | None = None,
    latency_ms: float | None = None,
    extra: dict | None = None,
) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "extra": extra or {},
        }
        lines = _load_lines()
        lines.append(json.dumps(entry))
        if len(lines) > MAX_LINES:
            lines = lines[-MAX_LINES:]
        LOG_FILE.write_text("\n".join(lines) + "\n")
    except Exception:  # noqa: BLE001
        pass


def get_recent(limit: int = 100) -> list[dict]:
    lines = _load_lines()
    results = []
    for line in reversed(lines[-limit:] if limit < len(lines) else lines):
        try:
            results.append(json.loads(line))
        except Exception:  # noqa: BLE001
            pass
    return results[:limit]


def activity_summary(limit: int = 1000) -> dict:
    lines = _load_lines()[-limit:]
    by_endpoint: dict[str, int] = {}
    by_method: dict[str, int] = {}
    latencies: list[float] = []
    total = 0
    for line in lines:
        try:
            entry = json.loads(line)
            total += 1
            ep = entry.get("endpoint", "unknown")
            m = entry.get("method", "unknown")
            by_endpoint[ep] = by_endpoint.get(ep, 0) + 1
            by_method[m] = by_method.get(m, 0) + 1
            if entry.get("latency_ms") is not None:
                latencies.append(float(entry["latency_ms"]))
        except Exception:  # noqa: BLE001
            pass
    return {
        "total_logged": total,
        "by_endpoint": by_endpoint,
        "by_method": by_method,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else None,
    }
