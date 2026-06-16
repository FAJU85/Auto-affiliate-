import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_VALID_STATUSES = ("pending", "confirmed", "paid", "rejected")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "commissions.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"entries": {}}


def _save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", dir=p.parent, delete=False, suffix=".tmp")
    try:
        json.dump(data, tmp)
        tmp.close()
        os.replace(tmp.name, p)
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record(
    transaction_id: str,
    product_id: str,
    network: str,
    amount: float,
    currency: str = "USD",
) -> bool:
    data = _load()
    if transaction_id in data["entries"]:
        return False
    data["entries"][transaction_id] = {
        "transaction_id": transaction_id,
        "product_id": product_id,
        "network": network,
        "amount": round(amount, 4),
        "currency": currency,
        "status": "pending",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _save(data)
    return True


def update_status(transaction_id: str, status: str) -> bool:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Status must be one of {_VALID_STATUSES}")
    data = _load()
    if transaction_id not in data["entries"]:
        return False
    data["entries"][transaction_id]["status"] = status
    data["entries"][transaction_id]["updated_at"] = _now_iso()
    _save(data)
    return True


def get(transaction_id: str) -> dict | None:
    return _load()["entries"].get(transaction_id)


def by_status(status: str) -> list[dict]:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Status must be one of {_VALID_STATUSES}")
    entries = _load()["entries"].values()
    return sorted([e for e in entries if e["status"] == status], key=lambda x: x["created_at"], reverse=True)


def by_network(network: str) -> list[dict]:
    entries = _load()["entries"].values()
    return [e for e in entries if e["network"].lower() == network.lower()]


def total_by_status(status: str, currency: str = "USD") -> float:
    entries = by_status(status)
    return round(sum(e["amount"] for e in entries if e["currency"] == currency), 4)


def commission_stats() -> dict:
    entries = list(_load()["entries"].values())
    stats: dict = {"total_transactions": len(entries)}
    for s in _VALID_STATUSES:
        amount = round(sum(e["amount"] for e in entries if e["status"] == s), 4)
        count = sum(1 for e in entries if e["status"] == s)
        stats[s] = {"count": count, "amount_usd": amount}
    networks: dict = {}
    for e in entries:
        n = e["network"]
        networks[n] = round(networks.get(n, 0) + e["amount"], 4)
    stats["by_network"] = networks
    return stats
