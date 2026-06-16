import importlib


def test_get_full_health_returns_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.system_health as m
    importlib.reload(m)
    result = m.get_full_health()
    assert isinstance(result, dict)


def test_get_full_health_has_required_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.system_health as m
    importlib.reload(m)
    result = m.get_full_health()
    for key in ("timestamp", "overall", "feeds", "latency", "commission_rates", "budget"):
        assert key in result


def test_overall_healthy_when_no_feeds(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.feed_health as fh
    import api.utils.latency_tracker as lt
    import api.utils.commission_rates as cr
    import api.utils.budget as bg
    import api.utils.system_health as m
    for mod in (fh, lt, cr, bg, m):
        importlib.reload(mod)
    result = m.get_full_health()
    assert result["overall"] == "healthy"


def test_budget_has_required_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.system_health as m
    importlib.reload(m)
    budget = m.get_full_health()["budget"]
    for key in ("daily_spend_usd", "monthly_est_usd", "cap_usd", "on_track"):
        assert key in budget


def test_timestamp_is_iso_string(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.system_health as m
    importlib.reload(m)
    ts = m.get_full_health()["timestamp"]
    from datetime import datetime
    assert datetime.fromisoformat(ts)


def test_commission_rates_present(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.system_health as m
    importlib.reload(m)
    rates = m.get_full_health()["commission_rates"]
    assert "default" in rates
