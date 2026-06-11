"""Unit tests for CircuitBreaker state transitions (PF-07)."""

import asyncio
import pytest
from api.utils.circuit_breaker import CircuitBreaker


class TestCircuitBreakerStates:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        assert cb.state == "closed"
        assert cb._failures == 0

    def test_single_failure_stays_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        assert cb.state == "closed"
        assert cb._failures == 1

    def test_threshold_failures_opens_breaker(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"

    def test_success_resets_failures_and_closes(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        assert cb._failures == 0

    def test_is_open_returns_true_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=999)
        cb.record_failure()
        assert cb.is_open() is True

    def test_is_open_returns_false_when_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        assert cb.is_open() is False

    def test_half_open_after_recovery_timeout(self):
        # recovery_timeout=0 means the CB transitions to half-open immediately
        # on first state check — it never shows "open" because monotonic() >= opened_at+0
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.state == "half-open"

    def test_reset_closes_breaker(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=999)
        cb.record_failure()
        assert cb.is_open()
        cb.reset()
        assert cb.state == "closed"
        assert cb._failures == 0

    def test_status_returns_correct_fields(self):
        cb = CircuitBreaker("myservice", failure_threshold=3, recovery_timeout=60)
        status = cb.status()
        assert status["name"] == "myservice"
        assert status["state"] == "closed"
        assert status["failures"] == 0
        assert status["threshold"] == 3

    @pytest.mark.asyncio
    async def test_call_raises_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=999)
        cb.record_failure()
        assert cb.is_open()
        with pytest.raises(RuntimeError, match="OPEN"):
            await cb.call(asyncio.sleep, 0)

    @pytest.mark.asyncio
    async def test_call_records_success(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        await cb.call(asyncio.sleep, 0)
        assert cb._failures == 0

    @pytest.mark.asyncio
    async def test_call_records_failure_on_exception(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)

        async def boom():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await cb.call(boom)
        assert cb._failures == 1
