"""Daily budget tracking in /data/budget.json (keyed by UTC date)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
BUDGET_FILE = DATA_DIR / "budget.json"


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
    return float(_load().get(_today(), 0.0))


def add_spend(amount: float) -> float:
    data = _load()
    day = _today()
    data[day] = round(float(data.get(day, 0.0)) + float(amount), 6)
    # prune to last 60 days worth of keys
    if len(data) > 60:
        for k in sorted(data.keys())[:-60]:
            data.pop(k, None)
    _save(data)
    return data[day]
