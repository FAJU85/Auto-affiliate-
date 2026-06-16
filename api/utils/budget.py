"""Daily budget tracking in /data/budget.json (keyed by UTC date).

FinOps:
  - Tracks actual API call costs per provider
  - Forecasts monthly spend based on daily run rate
  - Alerts when approaching cap
  - Computes ROI vs affiliate commission revenue
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR    = Path(os.environ.get("DATA_DIR", "/data"))
BUDGET_FILE = DATA_DIR / "budget.json"

# Estimated cost per run component (USD)
COST_PER_RUN = {
    "groq":    0.0000,   # Groq free tier
    "mistral": 0.0002,   # ~$0.0002 per caption @ mistral-small
    "bluesky": 0.0000,   # free
    "sovrn":   0.0000,   # free API
    "default": 0.001,    # conservative default
}

# Alert thresholds
SPEND_ALERT_PCT = 80   # warn when daily spend > 80% of cap
ROI_WARN_RATIO  = 1.0  # ROI below 1.0 means losing money


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load() -> dict:
    try:
        return json.loads(BUDGET_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(BUDGET_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(BUDGET_FILE)


def get_daily_spend() -> float:
    return float(_load().get(_today(), {}).get("total", 0.0)
                 if isinstance(_load().get(_today()), dict)
                 else _load().get(_today(), 0.0))


def add_spend(amount: float, provider: str = "default") -> float:
    data  = _load()
    day   = _today()
    entry = data.get(day, {})
    if not isinstance(entry, dict):
        entry = {"total": float(entry)}
    entry["total"]    = round(float(entry.get("total", 0.0)) + float(amount), 6)
    entry[provider]   = round(float(entry.get(provider, 0.0)) + float(amount), 6)
    data[day] = entry
    # Prune to last 90 days
    if len(data) > 90:
        for k in sorted(data.keys())[:-90]:
            data.pop(k, None)
    _save(data)
    return entry["total"]


def get_monthly_forecast(cap: float = 2.0) -> dict:
    """Estimate monthly spend and % of cap consumed based on last 7 days."""
    data = _load()
    today = _today()
    days_with_data = [
        v if not isinstance(v, dict) else v.get("total", 0.0)
        for k, v in data.items()
        if k <= today
    ][-7:]
    if not days_with_data:
        return {"daily_avg_usd": 0.0, "monthly_est_usd": 0.0, "cap_usd": cap, "cap_pct": 0.0, "on_track": True}
    daily_avg   = sum(days_with_data) / len(days_with_data)
    monthly_est = round(daily_avg * 30, 4)
    return {
        "daily_avg_usd":  round(daily_avg, 6),
        "monthly_est_usd": monthly_est,
        "cap_usd":        cap,
        "cap_pct":        round(monthly_est / cap * 100, 1) if cap else 0.0,
        "on_track":       monthly_est <= cap,
    }


def spend_alert(cap: float) -> dict | None:
    """Return an alert dict if daily spend is approaching or exceeding cap.

    Returns None when spend is comfortably within limits.
    """
    daily = get_daily_spend()
    if cap <= 0:
        return None
    pct = daily / cap * 100
    if pct >= 100:
        return {
            "level": "critical",
            "message": f"Daily spend ${daily:.4f} has EXCEEDED cap ${cap:.2f}",
            "pct_of_cap": round(pct, 1),
        }
    if pct >= SPEND_ALERT_PCT:
        return {
            "level": "warning",
            "message": f"Daily spend ${daily:.4f} is {pct:.0f}% of cap ${cap:.2f}",
            "pct_of_cap": round(pct, 1),
        }
    return None


def compute_roi(monthly_commission: float, monthly_spend: float) -> dict:
    """Compute ROI ratio and classify it.

    ROI = commission / spend. >1 means profitable; <1 means losing money.
    """
    if monthly_spend <= 0:
        roi = None  # no spend → infinite ROI (free tier)
        status = "free"
    else:
        roi = round(monthly_commission / monthly_spend, 2)
        if roi >= 10:
            status = "excellent"
        elif roi >= 3:
            status = "good"
        elif roi >= ROI_WARN_RATIO:
            status = "ok"
        else:
            status = "poor"

    return {
        "roi": roi,
        "status": status,
        "monthly_commission_usd": round(monthly_commission, 4),
        "monthly_spend_usd": round(monthly_spend, 4),
        "profitable": roi is None or roi >= ROI_WARN_RATIO,
    }


def revenue_forecast(runs: list[dict], days_history: int = 30) -> dict:
    """Project monthly commission revenue from recent run + conversion history.

    Args:
        runs: recent pipeline run records
        days_history: how many days of history to use for projection
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days_history)

    successful = [
        r for r in runs
        if r.get("success") and _parse_ts(r.get("timestamp", "")) > cutoff
    ]
    total_clicks = sum(int(r.get("clicks", 0)) for r in successful)
    # Commission: not tracked per-run yet, so estimate from click rate
    # Rough industry benchmark: ~1-2% conversion, avg $5 commission per sale
    avg_commission_per_click = 0.05  # conservative: $0.05 EPC
    projected_monthly = round(total_clicks * avg_commission_per_click * (30 / max(days_history, 1)), 4)

    return {
        "posts_analysed": len(successful),
        "total_clicks": total_clicks,
        "days_history": days_history,
        "projected_monthly_usd": projected_monthly,
        "epc_assumption_usd": avg_commission_per_click,
    }


def _parse_ts(ts_str: str) -> datetime:
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)
