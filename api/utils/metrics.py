"""Run history + dedup store in /data/metrics.json.

A "run" record looks like:
{
  timestamp, success, product, productSource, imageSource, qualityScore,
  captionChars, likes, reposts, durationMs, postUri, deeplink, trackingId,
  error, clicks
}
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEDUP_TTL_HOURS = int(os.environ.get("DEDUP_TTL_HOURS", "24"))   # 24h default — 55 products × 24h cycles cleanly at hourly cadence

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
METRICS_FILE = DATA_DIR / "metrics.json"

_MAX_RUNS = 500
_MAX_POSTED = 1000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    try:
        data = json.loads(METRICS_FILE.read_text())
    except Exception:
        data = {}
    data.setdefault("runs", [])
    data.setdefault("posted", {})  # key -> {ts, source}
    return data


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data["runs"] = data.get("runs", [])[-_MAX_RUNS:]
    tmp = str(METRICS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(METRICS_FILE)


# ── Runs ────────────────────────────────────────────────────────────────────

def record_run(run: dict) -> dict:
    data = _load()
    run.setdefault("timestamp", _now())
    run.setdefault("clicks", 0)
    data["runs"].append(run)
    _save(data)
    return run


def get_recent_runs(n: int = 50) -> list[dict]:
    runs = _load().get("runs", [])
    return runs[-n:]


def get_network_health(n: int = 100) -> dict:
    runs = get_recent_runs(n)
    health: dict = {}
    for r in runs:
        src = r.get("productSource")
        if not src:
            continue
        h = health.setdefault(src, {"attempts": 0, "success": 0})
        h["attempts"] += 1
        if r.get("success"):
            h["success"] += 1
    for src, h in health.items():
        h["rate"] = h["success"] / h["attempts"] if h["attempts"] else 0
    return health


# ── Dedup ───────────────────────────────────────────────────────────────────

def _dedup_key(url: str | None, name: str | None) -> str:
    return (str(url or "") + "|" + str(name or "")).strip().lower()


def was_recently_posted(url: str | None, name: str | None) -> bool:
    return was_posted_within(url, name, hours=DEDUP_TTL_HOURS)


def was_posted_within(url: str | None, name: str | None, hours: float = DEDUP_TTL_HOURS) -> bool:
    entry = _load().get("posted", {}).get(_dedup_key(url, name))
    if entry is None:
        return False
    try:
        posted_at = datetime.fromisoformat(entry.get("ts", ""))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return posted_at > cutoff
    except Exception:
        return False  # malformed ts → allow re-post


def mark_posted(url: str | None, name: str | None, source: str | None) -> None:
    data = _load()
    posted = data.setdefault("posted", {})
    posted[_dedup_key(url, name)] = {"ts": _now(), "source": source}
    if len(posted) > _MAX_POSTED:
        for k in sorted(posted, key=lambda x: posted[x].get("ts", ""))[: len(posted) - _MAX_POSTED]:
            posted.pop(k, None)
    _save(data)


def get_dedup_status() -> dict:
    posted = _load().get("posted", {})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUP_TTL_HOURS)
    active = 0
    for entry in posted.values():
        try:
            if datetime.fromisoformat(entry.get("ts", "")) > cutoff:
                active += 1
        except Exception:
            pass
    return {"count": len(posted), "activeCount": active, "ttlHours": DEDUP_TTL_HOURS}


def get_dedup_by_source() -> dict:
    posted = _load().get("posted", {})
    out: dict = {}
    for entry in posted.values():
        src = entry.get("source") or "unknown"
        out[src] = out.get(src, 0) + 1
    return out


def clear_posted_store() -> int:
    data = _load()
    n = len(data.get("posted", {}))
    data["posted"] = {}
    _save(data)
    return n


# ── Clicks ──────────────────────────────────────────────────────────────────

def record_click(tracking_id: str) -> dict | None:
    data = _load()
    target = None
    for r in data.get("runs", []):
        if r.get("trackingId") == tracking_id:
            r["clicks"] = int(r.get("clicks", 0)) + 1
            target = r
            break
    if target:
        _save(data)
    return target


def get_total_clicks() -> int:
    return sum(int(r.get("clicks", 0)) for r in _load().get("runs", []))




# ── Conversions ─────────────────────────────────────────────────────────────

def record_conversion(tracking_id: str, commission_usd: float, network: str, order_id: str = "") -> dict | None:
    """Record an affiliate conversion (postback from network).

    Called when a network pings POST /api/affiliate/postback after a purchase.
    Links the commission back to the run record that generated the click.
    """
    data = _load()
    target = None
    for r in data.get("runs", []):
        if r.get("trackingId") == tracking_id:
            conversions = r.setdefault("conversions", [])
            conversions.append({
                "ts": _now(),
                "commission_usd": round(commission_usd, 4),
                "network": network,
                "order_id": order_id,
            })
            r["totalCommissionUsd"] = round(
                sum(c["commission_usd"] for c in conversions), 4
            )
            target = r
            break
    if target:
        _save(data)
    return target


def get_total_commission() -> float:
    """Sum all recorded commission across all run history."""
    return round(
        sum(
            sum(c.get("commission_usd", 0) for c in r.get("conversions", []))
            for r in _load().get("runs", [])
        ),
        4,
    )


def get_commission_by_network() -> dict:
    """Commission earned per affiliate network."""
    out: dict = {}
    for r in _load().get("runs", []):
        for c in r.get("conversions", []):
            net = c.get("network", "unknown")
            out[net] = round(out.get(net, 0.0) + c.get("commission_usd", 0), 4)
    return out


def get_conversion_count() -> int:
    return sum(len(r.get("conversions", [])) for r in _load().get("runs", []))
def clear_run_history() -> int:
    """Purge all run records — resets SLO baseline. Use after fixing a systematic failure."""
    data = _load()
    n = len(data.get("runs", []))
    data["runs"] = []
    _save(data)
    return n
