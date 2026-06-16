import json
import os
import re
import tempfile
from pathlib import Path


def _data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def _path() -> Path:
    return _data_dir() / "blacklist.json"


def _load() -> dict:
    p = _path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"domains": [], "keywords": [], "product_ids": []}


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


def _normalize(value: str) -> str:
    return value.strip().lower()


def _validate_category(category: str) -> None:
    if category not in ("domains", "keywords", "product_ids"):
        raise ValueError(f"Unknown category {category!r}. Use: domains, keywords, product_ids")


def add(category: str, value: str) -> bool:
    _validate_category(category)
    data = _load()
    v = _normalize(value)
    if v not in data[category]:
        data[category].append(v)
        data[category].sort()
        _save(data)
        return True
    return False


def remove(category: str, value: str) -> bool:
    _validate_category(category)
    data = _load()
    v = _normalize(value)
    if v in data[category]:
        data[category].remove(v)
        _save(data)
        return True
    return False


def is_blocked_domain(url: str) -> bool:
    data = _load()
    url_lower = url.lower()
    return any(d in url_lower for d in data.get("domains", []))


def is_blocked_keyword(text: str) -> bool:
    data = _load()
    text_lower = text.lower()
    return any(re.search(r"\b" + re.escape(k) + r"\b", text_lower) for k in data.get("keywords", []))


def is_blocked_product(product_id: str) -> bool:
    data = _load()
    return _normalize(product_id) in data.get("product_ids", [])


def is_blocked(product: dict) -> bool:
    pid = product.get("id", "")
    url = product.get("url", "")
    title = product.get("title", "") + " " + product.get("description", "")
    return (
        (pid and is_blocked_product(pid))
        or (url and is_blocked_domain(url))
        or (title.strip() and is_blocked_keyword(title))
    )


def filter_products(products: list[dict]) -> list[dict]:
    return [p for p in products if not is_blocked(p)]


def list_blocked(category: str | None = None) -> dict:
    data = _load()
    if category:
        _validate_category(category)
        return {category: data.get(category, [])}
    return {k: data.get(k, []) for k in ("domains", "keywords", "product_ids")}


def blacklist_stats() -> dict:
    data = _load()
    return {
        "domains": len(data.get("domains", [])),
        "keywords": len(data.get("keywords", [])),
        "product_ids": len(data.get("product_ids", [])),
        "total": sum(len(data.get(k, [])) for k in ("domains", "keywords", "product_ids")),
    }
