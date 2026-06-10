"""Daily budget tracking in /data/budget.json (keyed by UTC date).

FinOps:
  - Tracks actual API call costs per provider
  - Forecasts monthly spend based on daily run rate
  - Alerts when approaching cap
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
        return {"daily_avg": 0.0, "monthly_est": 0.0, "cap_pct": 0.0}
    daily_avg   = sum(days_with_data) / len(days_with_data)
    monthly_est = round(daily_avg * 30, 4)
    return {
        "daily_avg_usd":  round(daily_avg, 6),
        "monthly_est_usd": monthly_est,
        "cap_usd":        cap,
        "cap_pct":        round(monthly_est / cap * 100, 1) if cap else 0.0,
        "on_track":       monthly_est <= cap,
    }
