"""Frontend & UX Sensor — checks dashboard.html integrity and API contract."""
from __future__ import annotations
import re
import time
from pathlib import Path

from .base import Severity, SensorReport

_DASHBOARD = Path(__file__).parent.parent.parent / "src" / "dashboard.html"

_REQUIRED_ENDPOINTS = [
    "/api/status", "/api/settings", "/api/run", "/api/stats",
    "/api/metrics", "/api/logs", "/api/circuit-breakers",
]

_REQUIRED_UI_SECTIONS = [
    "dashboard", "settings", "logs",
]

_REQUIRED_JS_FUNCTIONS = [
    "loadStatus", "loadAll",
]

# Keys the frontend reads from GET /api/settings response
_SETTINGS_KEYS_USED_BY_FRONTEND = [
    "bskyEnabled", "publishPlatforms", "schedulerEnabled",
    "postsPerDay", "maxPostLength",
]


def run() -> SensorReport:
    report = SensorReport("frontend")
    t0 = time.time()

    if not _DASHBOARD.exists():
        report.add("file", Severity.CRITICAL, "src/dashboard.html missing",
                   fix_hint="Restore dashboard.html from git history")
        report.duration_ms = (time.time() - t0) * 1000
        return report

    src = _DASHBOARD.read_text()
    size_kb = len(src.encode()) / 1024

    # 1. File size sanity (should be > 10 KB)
    if size_kb < 10:
        report.add("size", Severity.CRITICAL, f"dashboard.html suspiciously small ({size_kb:.1f} KB)",
                   fix_hint="Dashboard may have been truncated — restore from git")
    else:
        report.add("size", Severity.OK, f"dashboard.html is {size_kb:.0f} KB")

    # 2. API endpoint references
    for ep in _REQUIRED_ENDPOINTS:
        if ep in src:
            report.add("endpoint_ref", Severity.OK, f"Dashboard references {ep}")
        else:
            report.add("endpoint_ref", Severity.WARN, f"Dashboard missing reference to {ep}",
                       fix_hint=f"Check if {ep} functionality was removed from dashboard.html")

    # 3. UI section presence (looks for id= or section labels)
    for section in _REQUIRED_UI_SECTIONS:
        pattern = re.compile(section, re.IGNORECASE)
        if pattern.search(src):
            report.add("ui_section", Severity.OK, f"UI section '{section}' present")
        else:
            report.add("ui_section", Severity.WARN, f"UI section '{section}' not found in dashboard",
                       fix_hint=f"Re-add '{section}' section to src/dashboard.html")

    # 4. JS function presence
    for fn in _REQUIRED_JS_FUNCTIONS:
        if fn in src:
            report.add("js_fn", Severity.OK, f"JS function '{fn}' present")
        else:
            report.add("js_fn", Severity.CRITICAL, f"JS function '{fn}' missing from dashboard",
                       fix_hint=f"Restore function {fn}() in src/dashboard.html <script> block")

    # 5. Settings keys cross-check with DEFAULTS
    try:
        from api.utils.settings import DEFAULTS
        for key in _SETTINGS_KEYS_USED_BY_FRONTEND:
            if key not in DEFAULTS:
                report.add("settings_contract", Severity.CRITICAL,
                           f"Frontend key '{key}' missing from backend DEFAULTS",
                           fix_hint=f"Add '{key}' to DEFAULTS in api/utils/settings.py")
            else:
                report.add("settings_contract", Severity.OK, f"'{key}' in DEFAULTS ✓")
    except Exception as e:
        report.add("settings_contract", Severity.WARN,
                   "Could not verify settings contract", detail=str(e))

    # 6. No broken template references
    broken = re.findall(r'\{\{[^}]*\}\}', src)  # Jinja-style unfilled vars in static HTML
    if broken:
        report.add("template", Severity.WARN,
                   f"{len(broken)} unfilled template placeholders in dashboard",
                   detail=str(broken[:5]),
                   fix_hint="Dashboard may have template vars that weren't rendered")
    else:
        report.add("template", Severity.OK, "No unfilled template placeholders")

    report.duration_ms = (time.time() - t0) * 1000
    return report
