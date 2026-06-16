import time
from collections import defaultdict

_buckets: dict[str, list[float]] = defaultdict(list)

DEFAULT_LIMITS: dict[str, int] = {
    "/api/run": 10,
    "/api/preview": 20,
    "/api/variations": 30,
    "default": 60,
}


def _prune(timestamps: list[float], window: float = 60.0) -> list[float]:
    cutoff = time.monotonic() - window
    return [t for t in timestamps if t >= cutoff]


def is_allowed(endpoint: str, limit: int | None = None, window: float = 60.0) -> bool:
    if limit is None:
        limit = DEFAULT_LIMITS.get(endpoint, DEFAULT_LIMITS["default"])
    _buckets[endpoint] = _prune(_buckets[endpoint], window)
    if len(_buckets[endpoint]) >= limit:
        return False
    _buckets[endpoint].append(time.monotonic())
    return True


def request_count(endpoint: str, window: float = 60.0) -> int:
    _buckets[endpoint] = _prune(_buckets[endpoint], window)
    return len(_buckets[endpoint])


def reset(endpoint: str | None = None) -> None:
    if endpoint is None:
        _buckets.clear()
    else:
        _buckets.pop(endpoint, None)


def rate_limit_status() -> dict:
    now = time.monotonic()
    return {
        ep: {
            "count_last_60s": len([t for t in ts if t >= now - 60]),
            "limit": DEFAULT_LIMITS.get(ep, DEFAULT_LIMITS["default"]),
        }
        for ep, ts in _buckets.items()
        if ts
    }
