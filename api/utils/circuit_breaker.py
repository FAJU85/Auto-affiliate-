"""Simple in-process circuit breaker for external API calls.

States: CLOSED (normal) → OPEN (failing, reject fast) → HALF_OPEN (probe)

Usage:
    cb = CircuitBreaker("bluesky", failure_threshold=3, recovery_timeout=120)
    async with cb:
        await external_call()

AuthError is a permanent credential/permission failure — it is re-raised but
does NOT count as a circuit-breaking failure (so the breaker stays closed).
"""

import time
from dataclasses import dataclass, field
from typing import Callable


class AuthError(RuntimeError):
    """Permanent auth/permission failure — should not trip the circuit breaker."""


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3       # consecutive failures to open
    recovery_timeout: float = 120.0  # seconds before half-open probe
    _failures: int = field(default=0, init=False, repr=False)
    _opened_at: float = field(default=0.0, init=False, repr=False)
    _state: str = field(default="closed", init=False, repr=False)

    @property
    def state(self) -> str:
        if self._state == "open":
            if time.monotonic() - self._opened_at >= self.recovery_timeout:
                self._state = "half-open"
        return self._state

    def record_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()

    def is_open(self) -> bool:
        return self.state == "open"

    async def call(self, fn: Callable, *args, **kwargs):
        if self.is_open():
            raise RuntimeError(
                f"Circuit breaker '{self.name}' is OPEN — "
                f"backing off for {self.recovery_timeout}s after {self._failures} failures"
            )
        try:
            result = await fn(*args, **kwargs)
            self.record_success()
            return result
        except AuthError:
            # Permanent auth failure — don't penalise the breaker; just re-raise
            raise
        except Exception:
            self.record_failure()
            raise

    def reset(self) -> None:
        """Manually close the circuit breaker (operator override)."""
        self._failures = 0
        self._state = "closed"
        self._opened_at = 0.0

    def status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failures": self._failures,
            "threshold": self.failure_threshold,
            "openedAt": self._opened_at or None,
        }


# Global circuit breakers for each external service
bluesky_cb  = CircuitBreaker("bluesky",  failure_threshold=3, recovery_timeout=60)
groq_cb     = CircuitBreaker("groq",     failure_threshold=5, recovery_timeout=60)
mistral_cb  = CircuitBreaker("mistral",  failure_threshold=5, recovery_timeout=60)
sovrn_cb    = CircuitBreaker("sovrn",    failure_threshold=5, recovery_timeout=120)
mastodon_cb  = CircuitBreaker("mastodon",  failure_threshold=3, recovery_timeout=120)
x_cb         = CircuitBreaker("x",         failure_threshold=3, recovery_timeout=120)
threads_cb   = CircuitBreaker("threads",   failure_threshold=3, recovery_timeout=120)
tumblr_cb    = CircuitBreaker("tumblr",    failure_threshold=3, recovery_timeout=120)
facebook_cb  = CircuitBreaker("facebook",  failure_threshold=3, recovery_timeout=120)
instagram_cb = CircuitBreaker("instagram", failure_threshold=3, recovery_timeout=120)

_ALL: dict[str, CircuitBreaker] = {
    "bluesky":   bluesky_cb,
    "groq":      groq_cb,
    "mistral":   mistral_cb,
    "sovrn":     sovrn_cb,
    "mastodon":  mastodon_cb,
    "x":         x_cb,
    "threads":   threads_cb,
    "tumblr":    tumblr_cb,
    "facebook":  facebook_cb,
    "instagram": instagram_cb,
}


def all_statuses() -> list[dict]:
    return [cb.status() for cb in _ALL.values()]


def reset_breaker(name: str) -> bool:
    """Reset a named circuit breaker. Returns True if found."""
    cb = _ALL.get(name)
    if cb:
        cb.reset()
        return True
    return False


def reset_all() -> None:
    for cb in _ALL.values():
        cb.reset()
