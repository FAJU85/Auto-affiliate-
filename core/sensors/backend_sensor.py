"""Backend Sensor — checks FastAPI routes, imports, pipeline, and circuit breakers."""
from __future__ import annotations
import importlib
import subprocess
import sys
import time
from pathlib import Path

from .base import Severity, SensorReport

_REQUIRED_MODULES = [
    "api.main",
    "api.pipeline",
    "api.social_post",
    "api.utils.settings",
    "api.utils.metrics",
    "api.utils.circuit_breaker",
    "api.utils.product_scorer",
]

_REQUIRED_ROUTES = [
    "/health", "/api/status", "/api/stats", "/api/settings",
    "/api/run", "/api/metrics", "/api/circuit-breakers",
]

_CRITICAL_FUNCTIONS = {
    "api.pipeline": ["run_pipeline"],
    "api.utils.product_scorer": ["pick_best_with_freshness", "score_product"],
    "api.utils.circuit_breaker": ["CircuitBreaker", "AuthError"],
    "api.utils.settings": ["get_settings", "save_settings", "DEFAULTS"],
}


def run() -> SensorReport:
    report = SensorReport("backend")
    t0 = time.time()

    # 1. Import check
    for mod in _REQUIRED_MODULES:
        try:
            m = importlib.import_module(mod)
            importlib.reload(m)
            report.add("import", Severity.OK, f"{mod} imports cleanly")
        except Exception as e:
            report.add("import", Severity.CRITICAL, f"Cannot import {mod}",
                       detail=str(e),
                       fix_hint=f"Check {mod.replace('.', '/')} for syntax errors or broken deps")

    # 2. Critical symbol check
    for mod, symbols in _CRITICAL_FUNCTIONS.items():
        try:
            m = importlib.import_module(mod)
            for sym in symbols:
                if not hasattr(m, sym):
                    report.add("symbol", Severity.CRITICAL, f"{mod}.{sym} missing",
                               fix_hint=f"Restore {sym} in {mod.replace('.', '/')}.py")
                else:
                    report.add("symbol", Severity.OK, f"{mod}.{sym} present")
        except Exception as e:
            report.add("symbol", Severity.CRITICAL, f"Cannot inspect {mod}", detail=str(e))

    # 3. Route presence check (parse main.py statically)
    main_src = (Path(__file__).parent.parent.parent / "api" / "main.py").read_text()
    for route in _REQUIRED_ROUTES:
        if f'"{route}"' in main_src or f"'{route}'" in main_src:
            report.add("route", Severity.OK, f"Route {route} defined")
        else:
            report.add("route", Severity.CRITICAL, f"Route {route} missing from main.py",
                       fix_hint=f"Add @app.get('{route}') handler to api/main.py")

    # 4. DEFAULTS completeness
    try:
        from api.utils.settings import DEFAULTS
        required_keys = ["bskyEnabled", "publishPlatforms", "schedulerEnabled"]
        for k in required_keys:
            if k not in DEFAULTS:
                report.add("settings", Severity.WARN, f"DEFAULTS missing key '{k}'",
                           fix_hint="Add missing key to DEFAULTS in api/utils/settings.py")
            else:
                report.add("settings", Severity.OK, f"DEFAULTS['{k}'] present")
    except Exception as e:
        report.add("settings", Severity.CRITICAL, "Cannot load DEFAULTS", detail=str(e))

    # 5. pipeline.py imports product_scorer correctly
    pipeline_src = (Path(__file__).parent.parent.parent / "api" / "pipeline.py").read_text()
    if "pick_best_with_freshness" not in pipeline_src:
        report.add("pipeline", Severity.CRITICAL,
                   "pipeline.py does not import pick_best_with_freshness",
                   fix_hint="Restore: from .utils.product_scorer import pick_best_with_freshness")
    else:
        report.add("pipeline", Severity.OK, "pipeline.py imports pick_best_with_freshness")

    report.duration_ms = (time.time() - t0) * 1000
    return report
