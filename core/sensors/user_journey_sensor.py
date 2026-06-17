"""User Journey Sensor — traces the end-to-end affiliate pipeline flow."""
from __future__ import annotations
import importlib
import time
from pathlib import Path

from .base import Severity, SensorReport

# Ordered steps in the affiliate posting journey
_JOURNEY_STEPS = [
    ("feed_import",   "api.feeds.sovrn",              "get_sovrn_product"),
    ("normalizer",    "api.utils.feed_normalizer",     "normalize"),
    ("scorer",        "api.utils.product_scorer",      "score_product"),
    ("dedup",         "api.utils.dedup_fingerprint",   "fingerprint"),
    ("text_gen",      "api.ai.text",                   "generate_post_text"),
    ("post_social",   "api.social_post",               "post_to_platform"),
    ("metrics",       "api.utils.metrics",             "record_run"),
    ("settings",      "api.utils.settings",            "get_settings"),
]

_FEED_MODULES = ["sovrn", "takeads", "admitad", "travelpayouts"]


def run() -> SensorReport:
    report = SensorReport("user_journey")
    t0 = time.time()

    # 1. Trace each step — can the module be imported and does the function exist?
    for step, module, fn in _JOURNEY_STEPS:
        try:
            m = importlib.import_module(module)
            if hasattr(m, fn):
                report.add(f"step:{step}", Severity.OK,
                           f"Step '{step}': {module}.{fn} reachable")
            else:
                report.add(f"step:{step}", Severity.CRITICAL,
                           f"Step '{step}': {module}.{fn} missing",
                           fix_hint=f"Restore function '{fn}' in {module.replace('.', '/')}.py")
        except ImportError as e:
            report.add(f"step:{step}", Severity.CRITICAL,
                       f"Step '{step}': cannot import {module}",
                       detail=str(e),
                       fix_hint=f"Fix import error in {module.replace('.', '/')}.py")

    # 2. Feed modules reachable
    feeds_root = Path(__file__).parent.parent.parent / "api" / "feeds"
    for feed in _FEED_MODULES:
        feed_path = feeds_root / f"{feed}.py"
        if feed_path.exists():
            try:
                m = importlib.import_module(f"api.feeds.{feed}")
                report.add("feed", Severity.OK, f"Feed module api.feeds.{feed} importable")
            except Exception as e:
                report.add("feed", Severity.CRITICAL,
                           f"Feed api.feeds.{feed} import error", detail=str(e),
                           fix_hint=f"Fix syntax/import error in api/feeds/{feed}.py")
        else:
            report.add("feed", Severity.WARN, f"Feed module api/feeds/{feed}.py not found")

    # 3. Pipeline entry point
    try:
        from api.pipeline import run_pipeline
        report.add("pipeline_entry", Severity.OK, "api.pipeline.run_pipeline callable")
    except Exception as e:
        report.add("pipeline_entry", Severity.CRITICAL,
                   "api.pipeline.run_pipeline not callable", detail=str(e),
                   fix_hint="Check api/pipeline.py for broken imports or syntax errors")

    # 4. Circuit breaker guards the journey
    try:
        from api.utils.circuit_breaker import CircuitBreaker, AuthError
        cb = CircuitBreaker("sensor_test")
        report.add("circuit_breaker", Severity.OK, "CircuitBreaker instantiates correctly")
    except Exception as e:
        report.add("circuit_breaker", Severity.CRITICAL,
                   "CircuitBreaker broken", detail=str(e),
                   fix_hint="Restore api/utils/circuit_breaker.py")

    # 5. AuthError must not inherit from Exception subclass that trips CB
    try:
        from api.utils.circuit_breaker import AuthError
        assert issubclass(AuthError, RuntimeError), "AuthError must extend RuntimeError"
        report.add("auth_error", Severity.OK, "AuthError extends RuntimeError (won't trip CB)")
    except AssertionError as e:
        report.add("auth_error", Severity.CRITICAL, str(e),
                   fix_hint="Change AuthError base class to RuntimeError in circuit_breaker.py")
    except Exception as e:
        report.add("auth_error", Severity.CRITICAL, "AuthError check failed", detail=str(e))

    report.duration_ms = (time.time() - t0) * 1000
    return report
