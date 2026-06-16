import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.system_audit as m
    importlib.reload(m)
    return m


def test_run_audit_returns_dict(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.run_audit()
    assert isinstance(result, dict)


def test_run_audit_has_required_keys(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.run_audit()
    for key in ("timestamp", "total_checks", "passed", "failed", "overall", "checks"):
        assert key in result


def test_run_audit_checks_is_list(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert isinstance(m.run_audit()["checks"], list)


def test_run_audit_all_checks_have_name_and_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for check in m.run_audit()["checks"]:
        assert "name" in check
        assert "status" in check


def test_run_audit_passed_plus_failed_equals_total(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.run_audit()
    assert result["passed"] + result["failed"] == result["total_checks"]


def test_run_audit_overall_healthy_when_all_pass(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.run_audit()
    if result["failed"] == 0:
        assert result["overall"] == "healthy"


def test_run_audit_timestamp_is_valid_iso(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    ts = m.run_audit()["timestamp"]
    from datetime import datetime
    assert datetime.fromisoformat(ts)


def test_run_audit_total_checks_positive(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.run_audit()["total_checks"] > 0
