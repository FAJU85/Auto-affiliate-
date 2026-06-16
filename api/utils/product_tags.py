import json
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
TAGS_FILE = DATA_DIR / "product_tags.json"


def _load() -> dict:
    try:
        return json.loads(TAGS_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(TAGS_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(TAGS_FILE)


def _key(product_name: str) -> str:
    return product_name.lower().strip()


def add_tag(product_name: str, tag: str) -> list[str]:
    data = _load()
    k = _key(product_name)
    tags = data.get(k, [])
    tag = tag.lower().strip()
    if tag and tag not in tags:
        tags.append(tag)
    data[k] = tags
    _save(data)
    return tags


def remove_tag(product_name: str, tag: str) -> bool:
    data = _load()
    k = _key(product_name)
    tags = data.get(k, [])
    tag = tag.lower().strip()
    if tag in tags:
        tags.remove(tag)
        data[k] = tags
        _save(data)
        return True
    return False


def get_tags(product_name: str) -> list[str]:
    return _load().get(_key(product_name), [])


def has_tag(product_name: str, tag: str) -> bool:
    return tag.lower().strip() in get_tags(product_name)


def get_all_tags() -> dict:
    return _load()


def products_with_tag(tag: str) -> list[str]:
    tag = tag.lower().strip()
    return [name for name, tags in _load().items() if tag in tags]
