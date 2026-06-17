"""Frontend Components Sensor — checks individual dashboard UI components and API shape contracts."""
from __future__ import annotations
import re
import time
from pathlib import Path

from .base import Severity, SensorReport

_DASHBOARD = Path(__file__).parent.parent.parent / "src" / "dashboard.html"

# Component → signature patterns that must exist in dashboard.html
_COMPONENTS = {
    "status_panel":     [r"status", r"health|uptime"],
    "run_button":       [r"api/run", r"run|post now"],
    "settings_form":    [r"api/settings", r"save|submit"],
    "metrics_panel":    [r"api/metrics|api/stats", r"click|post"],
    "logs_panel":       [r"api/logs", r"log|error"],
    "platform_toggles": [r"twitter|bluesky|mastodon|instagram"],
    "circuit_breakers": [r"circuit.breaker|circuit_breaker"],
    "scheduler":        [r"schedule|interval"],
}

# API response shape contracts: endpoint → keys that must appear in dashboard parsing code
_API_CONTRACTS = {
    "/api/status":   ["status", "running"],
    "/api/settings": ["blueskyHandle", "postInterval"],
    "/api/stats":    ["total", "clicks"],
}

# Settings keys that appear in both DEFAULTS and the dashboard form
_SHARED_SETTINGS_KEYS = [
    "blueskyHandle", "blueskyAppPassword",
    "postInterval", "enabledPlatforms",
]


def run() -> SensorReport:
    report = SensorReport("frontend_components")
    t0 = time.time()

    if not _DASHBOARD.exists():
        report.add("dashboard", Severity.CRITICAL, "src/dashboard.html missing")
        report.duration_ms = (time.time() - t0) * 1000
        return report

    src = _DASHBOARD.read_text().lower()  # case-insensitive checks

    # 1. Component presence checks
    for component, patterns in _COMPONENTS.items():
        hits = [p for p in patterns if re.search(p, src, re.IGNORECASE)]
        if len(hits) == len(patterns):
            report.add(f"component:{component}", Severity.OK,
                       f"Component '{component}' detected (all {len(patterns)} patterns found)")
        elif hits:
            report.add(f"component:{component}", Severity.WARN,
                       f"Component '{component}' partially detected ({len(hits)}/{len(patterns)} patterns)",
                       fix_hint=f"Verify '{component}' is fully functional in dashboard.html")
        else:
            report.add(f"component:{component}", Severity.CRITICAL,
                       f"Component '{component}' not detected in dashboard.html",
                       fix_hint=f"Restore the '{component}' UI section in src/dashboard.html")

    # 2. API contract — key names referenced in dashboard JS
    raw_src = _DASHBOARD.read_text()
    for endpoint, keys in _API_CONTRACTS.items():
        for key in keys:
            if key in raw_src:
                report.add(f"contract:{endpoint}", Severity.OK,
                           f"Dashboard uses '{key}' from {endpoint}")
            else:
                report.add(f"contract:{endpoint}", Severity.WARN,
                           f"Dashboard may not use '{key}' from {endpoint}",
                           fix_hint=f"Verify dashboard parses '{key}' in response from {endpoint}")

    # 3. Settings key alignment
    try:
        from api.utils.settings import DEFAULTS
        for key in _SHARED_SETTINGS_KEYS:
            in_defaults = key in DEFAULTS
            in_dashboard = key in raw_src
            if in_defaults and in_dashboard:
                report.add(f"settings_sync:{key}", Severity.OK,
                           f"'{key}' in both DEFAULTS and dashboard")
            elif in_defaults and not in_dashboard:
                report.add(f"settings_sync:{key}", Severity.WARN,
                           f"'{key}' in DEFAULTS but not referenced in dashboard",
                           fix_hint=f"Add '{key}' field to dashboard settings form")
            elif not in_defaults and in_dashboard:
                report.add(f"settings_sync:{key}", Severity.CRITICAL,
                           f"'{key}' used in dashboard but missing from DEFAULTS",
                           fix_hint=f"Add '{key}' to DEFAULTS in api/utils/settings.py")
            else:
                report.add(f"settings_sync:{key}", Severity.WARN,
                           f"'{key}' missing from both DEFAULTS and dashboard")
    except Exception as e:
        report.add("settings_sync", Severity.WARN,
                   "Could not verify settings alignment", detail=str(e))

    # 4. No console.error left in production code (warns about debug leftovers)
    error_logs = re.findall(r'console\.error\([^)]+\)', raw_src)
    if len(error_logs) > 5:
        report.add("debug_code", Severity.WARN,
                   f"{len(error_logs)} console.error() calls in dashboard",
                   fix_hint="Review if any console.error() calls expose internal details")
    else:
        report.add("debug_code", Severity.OK,
                   f"console.error() usage within normal range ({len(error_logs)} calls)")

    report.duration_ms = (time.time() - t0) * 1000
    return report
