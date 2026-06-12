"""Unit tests for Four Golden Signals telemetry (utils/telemetry.py)."""

import time
from api.utils import telemetry


def _reset():
    telemetry._latency.clear()
    telemetry._errors.clear()
    telemetry._traffic.clear()
    telemetry._saturation.clear()


class TestRecordLatency:
    def setup_method(self):
        _reset()

    def test_increments_traffic(self):
        telemetry.record_latency("pipeline", 100.0, True)
        assert telemetry._traffic["pipeline"] == 1

    def test_increments_error_on_failure(self):
        telemetry.record_latency("pipeline", 50.0, False)
        assert telemetry._errors.get("pipeline", 0) == 1

    def test_no_error_on_success(self):
        telemetry.record_latency("pipeline", 50.0, True)
        assert telemetry._errors.get("pipeline", 0) == 0

    def test_accumulates_multiple(self):
        for _ in range(5):
            telemetry.record_latency("bluesky", 20.0, True)
        assert telemetry._traffic["bluesky"] == 5

    def test_latency_stored(self):
        telemetry.record_latency("sovrn", 75.0, True)
        samples = list(telemetry._latency["sovrn"])
        assert len(samples) == 1
        assert samples[0]["ms"] == 75.0
        assert samples[0]["ok"] is True


class TestRecordSaturation:
    def setup_method(self):
        _reset()

    def test_increments_saturation(self):
        telemetry.record_saturation("bluesky")
        assert telemetry._saturation["bluesky"] == 1

    def test_accumulates(self):
        telemetry.record_saturation("x")
        telemetry.record_saturation("x")
        assert telemetry._saturation["x"] == 2


class TestGoldenSignals:
    def setup_method(self):
        _reset()

    def test_returns_required_keys(self):
        sig = telemetry.golden_signals()
        assert "latency_p50_ms" in sig
        assert "latency_p99_ms" in sig
        assert "error_rate_pct" in sig
        assert "traffic_total" in sig
        assert "saturation_hits" in sig

    def test_empty_returns_empty_dicts(self):
        sig = telemetry.golden_signals()
        assert sig["traffic_total"] == {}
        assert sig["saturation_hits"] == {}

    def test_p50_p99_computed(self):
        for ms in range(1, 101):
            telemetry.record_latency("test", float(ms), True)
        sig = telemetry.golden_signals()
        assert "test" in sig["latency_p50_ms"]
        assert "test" in sig["latency_p99_ms"]
        assert sig["latency_p50_ms"]["test"] <= sig["latency_p99_ms"]["test"]

    def test_error_rate_100_all_failures(self):
        for _ in range(4):
            telemetry.record_latency("comp", 10.0, False)
        sig = telemetry.golden_signals()
        assert sig["error_rate_pct"]["comp"] == 100.0

    def test_traffic_reflects_counts(self):
        telemetry.record_latency("api", 5.0, True)
        telemetry.record_latency("api", 5.0, True)
        sig = telemetry.golden_signals()
        assert sig["traffic_total"]["api"] == 2

    def test_saturation_in_output(self):
        telemetry.record_saturation("mastodon")
        sig = telemetry.golden_signals()
        assert sig["saturation_hits"]["mastodon"] == 1


class TestTimer:
    def setup_method(self):
        _reset()

    def test_records_on_success(self):
        with telemetry.Timer("timer_test"):
            pass
        assert telemetry._traffic.get("timer_test", 0) == 1

    def test_records_failure_on_exception(self):
        try:
            with telemetry.Timer("timer_err") as t:
                t.success = False
                raise ValueError("test")
        except ValueError:
            pass
        assert telemetry._errors.get("timer_err", 0) == 1

    def test_success_flag_default_true(self):
        t = telemetry.Timer("x")
        assert t.success is True
