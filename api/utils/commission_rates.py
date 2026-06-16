"""Per-network affiliate commission rate storage.

Rates are stored in DATA_DIR/commission_rates.json.  Any saved rate overrides
the built-in DEFAULT_RATES dict.  Rates must be in [0.0, 1.0] (they represent
the commission fraction, e.g. 0.07 == 7 %).
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
RATES_FILE = DATA_DIR / "commission_rates.json"

DEFAULT_RATES: dict[str, float] = {
    "sovrn": 0.05,
    "takeads": 0.06,
    "admitad": 0.07,
    "travelpayouts": 0.08,
    "default": 0.05,
}


def _load() -> dict:
    try:
        return json.loads(RATES_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(RATES_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(RATES_FILE)


def get_all_rates() -> dict:
    """Return DEFAULT_RATES merged with any saved overrides."""
    merged = dict(DEFAULT_RATES)
    merged.update(_load())
    return merged


def get_rate(network: str) -> float:
    """Return commission rate for *network* (case-insensitive).

    Falls back to the "default" rate when the network is unknown.
    """
    key = network.lower()
    rates = get_all_rates()
    return rates.get(key, rates["default"])


def set_rate(network: str, rate: float) -> None:
    """Persist a commission rate for *network*.

    Raises ValueError when *rate* is outside [0.0, 1.0].
    """
    if rate < 0.0 or rate > 1.0:
        raise ValueError(f"rate must be between 0.0 and 1.0, got {rate}")
    data = _load()
    data[network.lower()] = float(rate)
    _save(data)


def estimated_monthly_commission(
    clicks: int,
    network: str = "default",
    conversion_rate: float = 0.01,
) -> float:
    """Estimate monthly affiliate commission revenue.

    Formula: clicks * conversion_rate * network_rate * 30

    Args:
        clicks: total clicks recorded
        network: affiliate network name (case-insensitive)
        conversion_rate: fraction of clicks that convert to sales

    Returns:
        Estimated monthly commission in USD, rounded to 4 decimal places.
    """
    return round(clicks * conversion_rate * get_rate(network) * 30, 4)
