import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

_VALID_STATUSES = ("running", "paused", "completed")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "ab_tests.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"tests": {}}


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


def _z_score(p1: float, n1: int, p2: float, n2: int) -> float | None:
    if n1 == 0 or n2 == 0:
        return None
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return None
    return round((p1 - p2) / se, 4)


def create_test(name: str, variants: list[str], metric: str = "clicks") -> str:
    if len(variants) < 2:
        raise ValueError("Need at least 2 variants")
    test_id = str(uuid.uuid4())[:8]
    data = _load()
    data["tests"][test_id] = {
        "id": test_id,
        "name": name,
        "metric": metric,
        "status": "running",
        "created_at": _now_iso(),
        "variants": {v: {"impressions": 0, "conversions": 0} for v in variants},
    }
    _save(data)
    return test_id


def get_test(test_id: str) -> dict | None:
    return _load()["tests"].get(test_id)


def record_impression(test_id: str, variant: str) -> bool:
    data = _load()
    test = data["tests"].get(test_id)
    if not test or variant not in test["variants"]:
        return False
    test["variants"][variant]["impressions"] += 1
    _save(data)
    return True


def record_conversion(test_id: str, variant: str) -> bool:
    data = _load()
    test = data["tests"].get(test_id)
    if not test or variant not in test["variants"]:
        return False
    test["variants"][variant]["conversions"] += 1
    _save(data)
    return True


def conversion_rate(test_id: str, variant: str) -> float | None:
    test = get_test(test_id)
    if not test or variant not in test["variants"]:
        return None
    v = test["variants"][variant]
    if v["impressions"] == 0:
        return None
    return round(v["conversions"] / v["impressions"], 4)


def winner(test_id: str) -> dict | None:
    test = get_test(test_id)
    if not test:
        return None
    rates = {}
    for name, v in test["variants"].items():
        if v["impressions"] > 0:
            rates[name] = v["conversions"] / v["impressions"]
    if not rates:
        return None
    best = max(rates, key=lambda k: rates[k])
    return {"variant": best, "rate": round(rates[best], 4)}


def significance(test_id: str, control: str, treatment: str) -> dict | None:
    test = get_test(test_id)
    if not test:
        return None
    if control not in test["variants"] or treatment not in test["variants"]:
        return None
    c = test["variants"][control]
    t = test["variants"][treatment]
    p_c = c["conversions"] / c["impressions"] if c["impressions"] else 0.0
    p_t = t["conversions"] / t["impressions"] if t["impressions"] else 0.0
    z = _z_score(p_t, t["impressions"], p_c, c["impressions"])
    is_significant = abs(z) >= 1.96 if z is not None else False
    lift = round((p_t - p_c) / p_c * 100, 2) if p_c > 0 else None
    return {
        "control": control,
        "treatment": treatment,
        "z_score": z,
        "is_significant": is_significant,
        "lift_pct": lift,
    }


def update_status(test_id: str, status: str) -> bool:
    if status not in _VALID_STATUSES:
        raise ValueError(f"Status must be one of {_VALID_STATUSES}")
    data = _load()
    if test_id not in data["tests"]:
        return False
    data["tests"][test_id]["status"] = status
    _save(data)
    return True


def list_tests(status: str | None = None) -> list[dict]:
    tests = list(_load()["tests"].values())
    if status:
        tests = [t for t in tests if t["status"] == status]
    return sorted(tests, key=lambda x: x["created_at"], reverse=True)
