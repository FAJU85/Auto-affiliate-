import json
import os
import time
from pathlib import Path
from contextlib import contextmanager

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
LATENCY_FILE = DATA_DIR / "latency.json"
MAX_SAMPLES = 50


def _load() -> dict:
    try:
        return json.loads(LATENCY_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(LATENCY_FILE) + ".tmp"
    Path(tmp).write_text(json.dumps(data, indent=2))
    Path(tmp).rename(LATENCY_FILE)


def record_latency(provider: str, latency_ms: float) -> None:
    data = _load()
    samples = data.get(provider, [])
    samples.append(round(latency_ms, 2))
    data[provider] = samples[-MAX_SAMPLES:]
    _save(data)


def avg_latency(provider: str) -> float | None:
    samples = _load().get(provider, [])
    return round(sum(samples) / len(samples), 2) if samples else None


def p95_latency(provider: str) -> float | None:
    samples = sorted(_load().get(provider, []))
    if not samples:
        return None
    idx = max(0, int(len(samples) * 0.95) - 1)
    return samples[idx]


def fastest_provider(providers: list[str]) -> str | None:
    avgs = {p: avg_latency(p) for p in providers}
    known = {p: v for p, v in avgs.items() if v is not None}
    if not known:
        return None
    return min(known, key=known.__getitem__)


def latency_summary() -> dict:
    data = _load()
    return {
        provider: {
            "avg_ms": avg_latency(provider),
            "p95_ms": p95_latency(provider),
            "samples": len(samples),
        }
        for provider, samples in data.items()
    }


@contextmanager
def track(provider: str):
    start = time.monotonic()
    try:
        yield
    finally:
        record_latency(provider, (time.monotonic() - start) * 1000)
