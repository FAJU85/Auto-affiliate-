"""Key Project Components Sensor — verifies critical files, structure, and data integrity."""
from __future__ import annotations
import json
import time
from pathlib import Path

from .base import Severity, SensorReport

_ROOT = Path(__file__).parent.parent.parent

_REQUIRED_FILES = {
    "api/main.py":                      "FastAPI app entry point",
    "api/pipeline.py":                  "Core posting pipeline",
    "api/social_post.py":               "Social platform posting logic",
    "api/utils/circuit_breaker.py":     "CircuitBreaker + AuthError",
    "api/utils/settings.py":            "Persistent settings with DEFAULTS",
    "api/utils/metrics.py":             "Run history and click tracking",
    "api/utils/product_scorer.py":      "Product scoring with pick_best_with_freshness",
    "api/feeds/sovrn.py":              "SOVRN feed (priority 1)",
    "api/feeds/takeads.py":            "TakeAds feed (priority 2)",
    "api/feeds/admitad.py":            "Admitad feed (priority 3)",
    "api/feeds/travelpayouts.py":      "Travelpayouts feed (priority 4)",
    "src/dashboard.html":              "Single-page frontend",
    "CLAUDE.md":                        "Project rules and branch config",
    "core/orchestrator.py":            "Intelligent test orchestrator",
}

_ADMITAD_REQUIRED_STRINGS = ["rzekl.com", "aff_short_key"]


def run() -> SensorReport:
    report = SensorReport("project_components")
    t0 = time.time()

    # 1. Required file existence
    for rel_path, description in _REQUIRED_FILES.items():
        full = _ROOT / rel_path
        if full.exists():
            size = full.stat().st_size
            if size < 50:
                report.add("file", Severity.WARN,
                           f"{rel_path} exists but is suspiciously small ({size} bytes)",
                           fix_hint=f"Verify {rel_path} was not accidentally emptied")
            else:
                report.add("file", Severity.OK, f"{rel_path} present ({size//1024}KB)")
        else:
            report.add("file", Severity.CRITICAL, f"{rel_path} MISSING — {description}",
                       fix_hint=f"Restore {rel_path} from git: git checkout HEAD {rel_path}")

    # 2. Admitad link integrity — rzekl.com wrapper must be preserved in affiliate_link_builder
    admitad_path = _ROOT / "api" / "utils" / "affiliate_link_builder.py"
    if admitad_path.exists():
        src = admitad_path.read_text()
        for required in _ADMITAD_REQUIRED_STRINGS:
            if required in src:
                report.add("admitad", Severity.OK, f"affiliate_link_builder.py contains '{required}'")
            else:
                report.add("admitad", Severity.CRITICAL,
                           f"affiliate_link_builder.py missing '{required}' — affiliate links will be broken",
                           fix_hint=f"Restore rzekl.com wrapper and aff_short_key in api/utils/affiliate_link_builder.py")

    # 3. settings.py DEFAULTS must not be empty
    settings_path = _ROOT / "api" / "utils" / "settings.py"
    if settings_path.exists():
        src = settings_path.read_text()
        if "DEFAULTS = {" in src and "}" in src:
            # Count keys
            import re
            keys = re.findall(r'^\s+"(\w+)":', src, re.MULTILINE)
            if len(keys) >= 5:
                report.add("defaults", Severity.OK, f"DEFAULTS has {len(keys)} keys")
            else:
                report.add("defaults", Severity.CRITICAL,
                           f"DEFAULTS only has {len(keys)} keys — likely truncated",
                           fix_hint="Restore DEFAULTS dict in api/utils/settings.py")
        else:
            report.add("defaults", Severity.CRITICAL, "DEFAULTS dict not found in settings.py",
                       fix_hint="Restore DEFAULTS in api/utils/settings.py")

    # 4. No credentials in tracked files (spot-check)
    for check_file in ["api/feeds/admitad.py", "api/utils/settings.py"]:
        path = _ROOT / check_file
        if path.exists():
            src = path.read_text()
            # Look for hardcoded tokens (simple heuristic)
            suspicious = [l.strip() for l in src.splitlines()
                          if any(kw in l.lower() for kw in ["password", "secret", "token"])
                          and "=" in l and "os.environ" not in l and "#" not in l.strip()[:5]
                          and "pragma: allowlist" not in l]
            if suspicious:
                report.add("credentials", Severity.CRITICAL,
                           f"Possible hardcoded credential in {check_file}",
                           detail=suspicious[0][:100],
                           fix_hint="Move credentials to environment variables")
            else:
                report.add("credentials", Severity.OK, f"No hardcoded credentials in {check_file}")

    # 5. pyproject.toml / requirements present
    has_reqs = (_ROOT / "requirements.txt").exists() or (_ROOT / "pyproject.toml").exists()
    if has_reqs:
        report.add("deps", Severity.OK, "Dependency file present")
    else:
        report.add("deps", Severity.WARN, "No requirements.txt or pyproject.toml found")

    report.duration_ms = (time.time() - t0) * 1000
    return report
