import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_STAGES = ("impression", "click", "view", "cart", "purchase")


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "funnel.json"


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


def _default_entry() -> dict:
    return {stage: 0 for stage in _STAGES}


def record(product_id: str, stage: str) -> None:
    if stage not in _STAGES:
        raise ValueError(f"Unknown stage {stage!r}. Valid: {_STAGES}")
    data = _load()
    if product_id not in data:
        data[product_id] = _default_entry()
    data[product_id][stage] = data[product_id].get(stage, 0) + 1
    data[product_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(data)


def get_funnel(product_id: str) -> dict | None:
    return _load().get(product_id)


def conversion_rate(product_id: str, from_stage: str = "click", to_stage: str = "purchase") -> float | None:
    entry = get_funnel(product_id)
    if not entry:
        return None
    top = entry.get(from_stage, 0)
    bottom = entry.get(to_stage, 0)
    if top == 0:
        return None
    return round(bottom / top, 4)


def funnel_summary() -> list[dict]:
    data = _load()
    result = []
    for pid, entry in data.items():
        clicks = entry.get("click", 0)
        purchases = entry.get("purchase", 0)
        result.append({
            "product_id": pid,
            **{s: entry.get(s, 0) for s in _STAGES},
            "click_to_purchase": round(purchases / clicks, 4) if clicks else None,
        })
    return sorted(result, key=lambda x: x.get("click", 0), reverse=True)


def reset_product(product_id: str) -> bool:
    data = _load()
    if product_id not in data:
        return False
    data[product_id] = _default_entry()
    _save(data)
    return True
