"""Tests for the 6-sensor monitoring system."""
import json
import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.sensors.base import Severity, Finding, SensorReport
from core.sensors import (
    backend_sensor, workflow_sensor, frontend_sensor,
    user_journey_sensor, project_components_sensor, frontend_components_sensor,
)
from core.sensor_runner import run_sensors


# ── Base types ────────────────────────────────────────────────────────────────

def test_sensor_report_default_ok():
    r = SensorReport("test")
    assert r.status == Severity.OK
    assert r.findings == []


def test_sensor_report_add_warn():
    r = SensorReport("test")
    r.add("chk", Severity.WARN, "something")
    assert r.status == Severity.WARN


def test_sensor_report_add_critical_overrides_warn():
    r = SensorReport("test")
    r.add("chk", Severity.WARN, "warn")
    r.add("chk2", Severity.CRITICAL, "crit")
    assert r.status == Severity.CRITICAL


def test_sensor_report_to_dict():
    r = SensorReport("test")
    r.add("chk", Severity.OK, "all good", fix_hint="nothing")
    d = r.to_dict()
    assert d["sensor"] == "test"
    assert d["status"] == "ok"
    assert len(d["findings"]) == 1
    assert d["findings"][0]["fix_hint"] == "nothing"


def test_finding_to_dict():
    f = Finding("s", "c", Severity.CRITICAL, "msg", "detail", "hint")
    d = f.to_dict()
    assert d["severity"] == "critical"
    assert d["fix_hint"] == "hint"


# ── Backend sensor ─────────────────────────────────────────────────────────────

def test_backend_sensor_runs():
    report = backend_sensor.run()
    assert report.sensor == "backend"
    assert report.status in (Severity.OK, Severity.WARN, Severity.CRITICAL)
    assert len(report.findings) > 0


def test_backend_sensor_detects_core_imports():
    report = backend_sensor.run()
    import_findings = [f for f in report.findings if f.check == "import"]
    assert len(import_findings) > 0


def test_backend_sensor_checks_routes():
    report = backend_sensor.run()
    route_findings = [f for f in report.findings if f.check == "route"]
    assert len(route_findings) > 0


def test_backend_sensor_checks_product_scorer_symbols():
    report = backend_sensor.run()
    symbol_findings = [f for f in report.findings if f.check == "symbol"]
    assert any("pick_best_with_freshness" in f.message for f in symbol_findings)


# ── Workflow sensor ────────────────────────────────────────────────────────────

def test_workflow_sensor_runs():
    report = workflow_sensor.run()
    assert report.sensor == "workflow"
    assert len(report.findings) > 0


def test_workflow_sensor_checks_ruff():
    report = workflow_sensor.run()
    ruff_findings = [f for f in report.findings if f.check == "ruff"]
    assert len(ruff_findings) == 1


def test_workflow_sensor_checks_qa_gate():
    report = workflow_sensor.run()
    qa_findings = [f for f in report.findings if f.check == "qa_gate"]
    assert len(qa_findings) > 0


def test_workflow_sensor_checks_claude_md():
    report = workflow_sensor.run()
    branch_findings = [f for f in report.findings if f.check == "branch"]
    assert len(branch_findings) == 1


# ── Frontend sensor ────────────────────────────────────────────────────────────

def test_frontend_sensor_runs():
    report = frontend_sensor.run()
    assert report.sensor == "frontend"
    assert len(report.findings) > 0


def test_frontend_sensor_checks_file_size():
    report = frontend_sensor.run()
    size_findings = [f for f in report.findings if f.check == "size"]
    assert len(size_findings) == 1


def test_frontend_sensor_checks_js_functions():
    report = frontend_sensor.run()
    js_findings = [f for f in report.findings if f.check == "js_fn"]
    assert len(js_findings) > 0


def test_frontend_sensor_checks_settings_contract():
    report = frontend_sensor.run()
    contract_findings = [f for f in report.findings if f.check == "settings_contract"]
    assert len(contract_findings) > 0


# ── User journey sensor ────────────────────────────────────────────────────────

def test_user_journey_sensor_runs():
    report = user_journey_sensor.run()
    assert report.sensor == "user_journey"
    assert len(report.findings) > 0


def test_user_journey_checks_pipeline_entry():
    report = user_journey_sensor.run()
    pipeline_findings = [f for f in report.findings if f.check == "pipeline_entry"]
    assert len(pipeline_findings) == 1


def test_user_journey_checks_circuit_breaker():
    report = user_journey_sensor.run()
    cb_findings = [f for f in report.findings if f.check == "circuit_breaker"]
    assert len(cb_findings) == 1


def test_user_journey_checks_auth_error():
    report = user_journey_sensor.run()
    auth_findings = [f for f in report.findings if f.check == "auth_error"]
    assert len(auth_findings) == 1
    assert auth_findings[0].severity == Severity.OK


# ── Project components sensor ──────────────────────────────────────────────────

def test_project_components_sensor_runs():
    report = project_components_sensor.run()
    assert report.sensor == "project_components"
    assert len(report.findings) > 0


def test_project_components_checks_admitad_wrapper():
    report = project_components_sensor.run()
    admitad_findings = [f for f in report.findings if f.check == "admitad"]
    # Should find rzekl.com and aff_short_key
    assert len(admitad_findings) >= 1


def test_project_components_checks_settings_defaults():
    report = project_components_sensor.run()
    defaults_findings = [f for f in report.findings if f.check == "defaults"]
    assert len(defaults_findings) == 1


def test_project_components_checks_required_files():
    report = project_components_sensor.run()
    file_findings = [f for f in report.findings if f.check == "file"]
    assert len(file_findings) >= 5


# ── Frontend components sensor ─────────────────────────────────────────────────

def test_frontend_components_sensor_runs():
    report = frontend_components_sensor.run()
    assert report.sensor == "frontend_components"
    assert len(report.findings) > 0


def test_frontend_components_checks_ui_components():
    report = frontend_components_sensor.run()
    comp_findings = [f for f in report.findings if f.check.startswith("component:")]
    assert len(comp_findings) > 0


def test_frontend_components_checks_settings_sync():
    report = frontend_components_sensor.run()
    sync_findings = [f for f in report.findings if f.check.startswith("settings_sync:")]
    assert len(sync_findings) > 0


# ── Runner integration ─────────────────────────────────────────────────────────

def test_run_all_sensors_returns_dict():
    results = run_sensors()
    assert "overall" in results
    assert "sensors" in results
    assert "duration_ms" in results
    assert set(results["sensors"].keys()) == {
        "backend", "workflow", "frontend",
        "user_journey", "project_components", "frontend_components",
    }


def test_run_single_sensor():
    results = run_sensors(["backend"])
    assert "backend" in results["sensors"]
    assert "workflow" not in results["sensors"]


def test_runner_overall_reflects_worst():
    results = run_sensors()
    statuses = [s["status"] for s in results["sensors"].values()]
    if "critical" in statuses:
        assert results["overall"] == "critical"
    elif "warn" in statuses:
        assert results["overall"] in ("warn", "critical")
    else:
        assert results["overall"] == "ok"


def test_runner_json_serializable():
    results = run_sensors()
    # Should not raise
    json_str = json.dumps(results)
    parsed = json.loads(json_str)
    assert parsed["overall"] in ("ok", "warn", "critical")
