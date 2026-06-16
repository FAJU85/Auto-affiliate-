import csv
import io
import json
from datetime import datetime, timezone


def _flatten(result: dict) -> dict:
    flat: dict = {}
    for k, v in result.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                flat[f"{k}_{sk}"] = sv
        else:
            flat[k] = v
    return flat


def to_json(results: list[dict], indent: int = 2) -> str:
    return json.dumps(results, indent=indent, default=str)


def to_csv(results: list[dict]) -> str:
    if not results:
        return ""
    flat_rows = [_flatten(r) for r in results]
    all_keys: list[str] = []
    seen: set[str] = set()
    for row in flat_rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore", restval="")
    writer.writeheader()
    writer.writerows(flat_rows)
    return buf.getvalue()


def to_markdown(results: list[dict]) -> str:
    if not results:
        return "_No results_\n"
    flat_rows = [_flatten(r) for r in results]
    all_keys: list[str] = []
    seen: set[str] = set()
    for row in flat_rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    header = "| " + " | ".join(all_keys) + " |"
    sep = "| " + " | ".join("---" for _ in all_keys) + " |"
    rows = []
    for row in flat_rows:
        cells = [str(row.get(k, "")) for k in all_keys]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep] + rows) + "\n"


def export_summary(results: list[dict]) -> dict:
    if not results:
        return {"exported_at": datetime.now(timezone.utc).isoformat(), "count": 0, "variants": []}
    variants = list({r.get("variant", r.get("name", "")) for r in results})
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "variants": sorted(variants),
    }
