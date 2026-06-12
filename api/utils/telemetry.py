"""Four Golden Signals telemetry — in-process ring buffers.

Tracks Latency, Traffic (request counts), Errors, and Saturation
without requiring an external monitoring system.
"""

import time
from collections import deque
from threading import Lock


_lock = Lock()

# Rolling window of latency samples per component (last 200)
_latency: dict[str, deque] = {}
# Error counts per component
_errors: dict[str, int] = {}
# Request counts per component
_traffic: dict[str, int] = {}
# Saturation markers (rate-limit hits)
_saturation: dict[str, int] = {}


def _component_latency(component: str) -> deque:
    if component not in _latency:
        _latency[component] = deque(maxlen=200)
    return _latency[component]


def record_latency(component: str, duration_ms: float, success: bool) -> None:
    with _lock:
        _component_latency(component).append({
            "ts": time.time(), "ms": duration_ms, "ok": success
        })
        _traffic[component] = _traffic.get(component, 0) + 1
        if not success:
            _errors[component] = _errors.get(component, 0) + 1


def record_saturation(component: str) -> None:
    with _lock:
        _saturation[component] = _saturation.get(component, 0) + 1


def golden_signals() -> dict:
    """Return the Four Golden Signals as a single dict."""
    with _lock:
        latency_p50 = {}
        latency_p99 = {}
        error_rate = {}
        for component, samples in _latency.items():
            if not samples:
                continue
            ms_values = sorted(s["ms"] for s in samples)
            n = len(ms_values)
            latency_p50[component] = ms_values[int(n * 0.50)]
            latency_p99[component] = ms_values[min(int(n * 0.99), n - 1)]
            recent = [s for s in samples if time.time() - s["ts"] < 3600]
            if recent:
                error_rate[component] = round(
                    sum(1 for s in recent if not s["ok"]) / len(recent) * 100, 1
                )
        return {
            "latency_p50_ms": latency_p50,
            "latency_p99_ms": latency_p99,
            "error_rate_pct": error_rate,
            "traffic_total": dict(_traffic),
            "saturation_hits": dict(_saturation),
        }


class Timer:
    """Context manager that records latency on exit."""
    def __init__(self, component: str):
        self.component = component
        self._start = 0.0
        self.success = True

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, *_):
        ms = (time.monotonic() - self._start) * 1000
        if exc_type is not None:
            self.success = False
        record_latency(self.component, ms, self.success)
