import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "coupons.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


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


def add_coupon(
    code: str,
    product_id: str = "",
    discount: str = "",
    expires_at: str = "",
    description: str = "",
) -> dict:
    data = _load()
    key = code.upper().strip()
    entry = {
        "code": key,
        "product_id": product_id,
        "discount": discount,
        "expires_at": expires_at,
        "description": description,
        "uses": 0,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    data[key] = entry
    _save(data)
    return entry


def use_coupon(code: str) -> bool:
    data = _load()
    key = code.upper().strip()
    if key not in data:
        return False
    data[key]["uses"] = data[key].get("uses", 0) + 1
    data[key]["last_used"] = datetime.now(timezone.utc).isoformat()
    _save(data)
    return True


def get_coupon(code: str) -> dict | None:
    return _load().get(code.upper().strip())


def is_expired(code: str) -> bool:
    entry = get_coupon(code)
    if not entry or not entry.get("expires_at"):
        return False
    try:
        exp = datetime.fromisoformat(entry["expires_at"].replace("Z", "+00:00"))
        return datetime.now(timezone.utc) > exp
    except Exception:
        return False


def list_coupons(product_id: str = "", active_only: bool = False) -> list[dict]:
    data = _load()
    coupons = list(data.values())
    if product_id:
        coupons = [c for c in coupons if c.get("product_id") == product_id]
    if active_only:
        coupons = [c for c in coupons if not is_expired(c["code"])]
    return sorted(coupons, key=lambda x: x["added_at"], reverse=True)


def delete_coupon(code: str) -> bool:
    data = _load()
    key = code.upper().strip()
    if key not in data:
        return False
    del data[key]
    _save(data)
    return True


def coupon_stats() -> dict:
    data = _load()
    coupons = list(data.values())
    expired = sum(1 for c in coupons if is_expired(c["code"]))
    return {
        "total": len(coupons),
        "active": len(coupons) - expired,
        "expired": expired,
        "total_uses": sum(c.get("uses", 0) for c in coupons),
    }
