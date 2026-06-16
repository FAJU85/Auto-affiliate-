import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CAD": 1.36,
    "AUD": 1.53,
    "JPY": 157.0,
    "CHF": 0.90,
    "SEK": 10.5,
    "NOK": 10.6,
    "DKK": 6.88,
    "PLN": 3.95,
    "BRL": 5.10,
    "MXN": 17.5,
    "INR": 83.5,
}

_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "CAD": "CA$", "AUD": "AU$", "CHF": "CHF", "SEK": "kr",
    "NOK": "kr", "DKK": "kr", "PLN": "zł", "BRL": "R$",
    "MXN": "MX$", "INR": "₹",
}


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "exchange_rates.json"


def _load_rates() -> dict:
    p = _path()
    if p.exists():
        try:
            stored = json.loads(p.read_text())
            return stored.get("rates", _DEFAULT_RATES)
        except Exception:
            pass
    return dict(_DEFAULT_RATES)


def _save_rates(rates: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", dir=p.parent, delete=False, suffix=".tmp")
    try:
        json.dump({"rates": rates, "updated_at": datetime.now(timezone.utc).isoformat()}, tmp)
        tmp.close()
        os.replace(tmp.name, p)
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise


def set_rate(currency: str, rate_vs_usd: float) -> None:
    rates = _load_rates()
    rates[currency.upper()] = rate_vs_usd
    _save_rates(rates)


def get_rate(currency: str) -> float | None:
    return _load_rates().get(currency.upper())


def convert(amount: float, from_currency: str, to_currency: str) -> float:
    rates = _load_rates()
    src = from_currency.upper()
    dst = to_currency.upper()
    if src not in rates:
        raise ValueError(f"Unknown currency: {src}")
    if dst not in rates:
        raise ValueError(f"Unknown currency: {dst}")
    usd = amount / rates[src]
    return round(usd * rates[dst], 4)


def format_price(amount: float, currency: str) -> str:
    currency = currency.upper()
    symbol = _SYMBOLS.get(currency, currency + " ")
    if currency == "JPY":
        return f"{symbol}{int(amount):,}"
    return f"{symbol}{amount:,.2f}"


def convert_and_format(amount: float, from_currency: str, to_currency: str) -> str:
    converted = convert(amount, from_currency, to_currency)
    return format_price(converted, to_currency)


def list_currencies() -> list[str]:
    return sorted(_load_rates().keys())


def rates_summary() -> dict:
    rates = _load_rates()
    return {"base": "USD", "currencies": len(rates), "rates": rates}
