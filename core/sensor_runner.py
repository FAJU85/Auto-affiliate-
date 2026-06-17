#!/usr/bin/env python3
"""
Sensor Runner — executes all 6 sensors, emits structured triggers on failure.

Usage:
    python core/sensor_runner.py                   # run all sensors
    python core/sensor_runner.py --sensor backend  # run one sensor
    python core/sensor_runner.py --json            # machine-readable output
    python core/sensor_runner.py --fix-hints       # show fix hints only
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

from core.sensors.base import Severity, SensorReport
from core.sensors import (
    backend_sensor,
    workflow_sensor,
    frontend_sensor,
    user_journey_sensor,
    project_components_sensor,
    frontend_components_sensor,
)

_SENSORS = {
    "backend":             backend_sensor,
    "workflow":            workflow_sensor,
    "frontend":            frontend_sensor,
    "user_journey":        user_journey_sensor,
    "project_components":  project_components_sensor,
    "frontend_components": frontend_components_sensor,
}

_TRIGGER_LOG = _ROOT / "data" / "sensor_triggers.jsonl"


def _emit_trigger(report: SensorReport) -> None:
    """Write a trigger record to the trigger log for automated response."""
    _TRIGGER_LOG.parent.mkdir(parents=True, exist_ok=True)
    trigger = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "trigger": "sensor_failure",
        "sensor": report.sensor,
        "status": report.status.value,
        "critical": [f.to_dict() for f in report.findings if f.severity == Severity.CRITICAL],
        "warnings": [f.to_dict() for f in report.findings if f.severity == Severity.WARN],
        "fix_hints": list({f.fix_hint for f in report.findings if f.fix_hint and f.severity != Severity.OK}),
    }
    with open(_TRIGGER_LOG, "a") as fh:
        fh.write(json.dumps(trigger) + "\n")


def run_sensors(names: list[str] | None = None) -> dict:
    """Run selected (or all) sensors and return aggregated results."""
    to_run = {k: v for k, v in _SENSORS.items() if not names or k in names}
    results = {}
    overall_status = Severity.OK
    t_total = time.time()

    for name, module in to_run.items():
        try:
            report = module.run()
        except Exception as e:
            report = SensorReport(name)
            report.add("sensor_crash", Severity.CRITICAL,
                       f"Sensor '{name}' crashed", detail=str(e),
                       fix_hint=f"Fix core/sensors/{name}_sensor.py")

        results[name] = report
        if report.status == Severity.CRITICAL:
            overall_status = Severity.CRITICAL
            _emit_trigger(report)
        elif report.status == Severity.WARN and overall_status == Severity.OK:
            overall_status = Severity.WARN

    return {
        "overall": overall_status.value,
        "duration_ms": round((time.time() - t_total) * 1000, 1),
        "ts": datetime.now(timezone.utc).isoformat(),
        "sensors": {k: v.to_dict() for k, v in results.items()},
    }


def _print_report(results: dict, fix_hints_only: bool = False) -> None:
    _STATUS_ICON = {"ok": "✅", "warn": "⚠️ ", "critical": "❌"}
    overall = results["overall"]
    icon = _STATUS_ICON.get(overall, "?")
    print(f"\n{'='*60}")
    print(f" SENSOR SYSTEM  {icon} {overall.upper()}  ({results['duration_ms']:.0f}ms)")
    print(f"{'='*60}")

    for sensor_name, sensor in results["sensors"].items():
        s_icon = _STATUS_ICON.get(sensor["status"], "?")
        print(f"\n{s_icon} {sensor_name.upper().replace('_', ' ')} ({sensor['duration_ms']:.0f}ms)")
        if fix_hints_only:
            for f in sensor["findings"]:
                if f["fix_hint"] and f["severity"] != "ok":
                    print(f"   [{f['severity'].upper()}] {f['message']}")
                    print(f"   → {f['fix_hint']}")
        else:
            for f in sensor["findings"]:
                icon_f = _STATUS_ICON.get(f["severity"], "?")
                print(f"   {icon_f} [{f['check']}] {f['message']}")
                if f["severity"] != "ok":
                    if f.get("detail"):
                        for line in f["detail"].splitlines()[:3]:
                            print(f"      {line}")
                    if f.get("fix_hint"):
                        print(f"      → FIX: {f['fix_hint']}")

    # Summary
    all_findings = [f for s in results["sensors"].values() for f in s["findings"]]
    n_crit = sum(1 for f in all_findings if f["severity"] == "critical")
    n_warn = sum(1 for f in all_findings if f["severity"] == "warn")
    n_ok   = sum(1 for f in all_findings if f["severity"] == "ok")
    print(f"\n{'─'*60}")
    print(f" {n_ok} OK  |  {n_warn} WARN  |  {n_crit} CRITICAL")
    if n_crit > 0:
        print(f" ⚡ {n_crit} trigger(s) written to data/sensor_triggers.jsonl")
    print(f"{'='*60}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all project sensors")
    parser.add_argument("--sensor", nargs="+", choices=list(_SENSORS),
                        help="Run specific sensors only")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fix-hints", action="store_true",
                        help="Show fix hints only (no OK findings)")
    args = parser.parse_args()

    results = run_sensors(args.sensor)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        _print_report(results, fix_hints_only=args.fix_hints)

    # Exit 1 if any critical
    return 1 if results["overall"] == "critical" else 0


if __name__ == "__main__":
    sys.exit(main())
