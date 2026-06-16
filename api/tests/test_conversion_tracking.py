"""Tests for affiliate conversion postback and revenue tracking."""

import os
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("conv_data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ.pop("POSTBACK_SECRET", None)

    import importlib
    import api.utils.metrics as mmod
    mmod.DATA_DIR = data_dir
    mmod.METRICS_FILE = data_dir / "metrics.json"
    importlib.reload(mmod)

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield {"client": c, "data_dir": data_dir, "metrics": mmod}


# ── metrics.record_conversion unit ───────────────────────────────────────────

class TestRecordConversion:
    def test_returns_none_for_unknown_tracking_id(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)

        result = m.record_conversion("nonexistent", 5.0, "sovrn")
        assert result is None

    def test_records_commission_on_matching_run(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)

        m.record_run({
            "trackingId": "abc123",
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        result = m.record_conversion("abc123", 4.20, "sovrn", "ORDER-1")
        assert result is not None
        assert result["totalCommissionUsd"] == pytest.approx(4.20)
        assert len(result["conversions"]) == 1
        assert result["conversions"][0]["commission_usd"] == pytest.approx(4.20)
        assert result["conversions"][0]["network"] == "sovrn"
        assert result["conversions"][0]["order_id"] == "ORDER-1"

    def test_accumulates_multiple_conversions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)

        m.record_run({
            "trackingId": "multi456",
            "success": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        m.record_conversion("multi456", 2.50, "sovrn")
        result = m.record_conversion("multi456", 3.75, "sovrn")
        assert result["totalCommissionUsd"] == pytest.approx(6.25)
        assert len(result["conversions"]) == 2

    def test_get_total_commission_sums_all(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)

        m.record_run({"trackingId": "t1", "success": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        m.record_run({"trackingId": "t2", "success": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        m.record_conversion("t1", 3.00, "sovrn")
        m.record_conversion("t2", 7.00, "takeads")
        assert m.get_total_commission() == pytest.approx(10.00)

    def test_get_commission_by_network(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)

        m.record_run({"trackingId": "n1", "success": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        m.record_run({"trackingId": "n2", "success": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        m.record_conversion("n1", 5.0, "sovrn")
        m.record_conversion("n2", 8.0, "admitad")
        by_net = m.get_commission_by_network()
        assert by_net.get("sovrn") == pytest.approx(5.0)
        assert by_net.get("admitad") == pytest.approx(8.0)

    def test_get_conversion_count(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)

        m.record_run({"trackingId": "cnt1", "success": True, "timestamp": datetime.now(timezone.utc).isoformat()})
        m.record_conversion("cnt1", 1.0, "sovrn")
        m.record_conversion("cnt1", 2.0, "sovrn")
        assert m.get_conversion_count() == 2


# ── POST /api/affiliate/postback ──────────────────────────────────────────────

class TestPostbackEndpoint:
    def _seed_run(self, m, tid="track001"):
        m.record_run({
            "trackingId": tid,
            "success": True,
            "deeplink": "https://amazon.com/dp/B001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def test_postback_json_body_returns_ok(self, client):
        c, m = client["client"], client["metrics"]
        self._seed_run(m, "pb_json_01")
        r = c.post("/api/affiliate/postback", json={
            "tracking_id": "pb_json_01",
            "commission_usd": 6.50,
            "network": "sovrn",
            "order_id": "ORD-999",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["commission_usd"] == pytest.approx(6.50)
        assert data["network"] == "sovrn"

    def test_postback_query_params_returns_ok(self, client):
        c, m = client["client"], client["metrics"]
        self._seed_run(m, "pb_qs_01")
        r = c.post("/api/affiliate/postback?tid=pb_qs_01&commission=3.75&network=takeads")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_postback_unknown_tracking_id_returns_error(self, client):
        c = client["client"]
        r = c.post("/api/affiliate/postback", json={
            "tracking_id": "nonexistent-xyz",
            "commission_usd": 1.0,
            "network": "sovrn",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_postback_missing_tracking_id_returns_error(self, client):
        c = client["client"]
        r = c.post("/api/affiliate/postback", json={"commission_usd": 5.0, "network": "sovrn"})
        assert r.status_code == 200
        assert r.json()["ok"] is False
        assert "tracking_id" in r.json()["error"]

    def test_postback_negative_commission_returns_error(self, client):
        c, m = client["client"], client["metrics"]
        self._seed_run(m, "pb_neg_01")
        r = c.post("/api/affiliate/postback", json={
            "tracking_id": "pb_neg_01",
            "commission_usd": -1.0,
            "network": "sovrn",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_postback_with_secret_rejects_bad_sig(self, client, monkeypatch):
        monkeypatch.setenv("POSTBACK_SECRET", "mysecret")
        c, m = client["client"], client["metrics"]
        self._seed_run(m, "pb_sig_01")
        r = c.post("/api/affiliate/postback?tid=pb_sig_01&commission=1.0&network=sovrn&sig=badsig")
        assert r.status_code == 403
        monkeypatch.delenv("POSTBACK_SECRET")

    def test_postback_with_valid_sig_passes(self, client, monkeypatch):
        import hmac
        import hashlib
        monkeypatch.setenv("POSTBACK_SECRET", "mysecret")
        c, m = client["client"], client["metrics"]
        self._seed_run(m, "pb_sig_02")
        sig = hmac.new(b"mysecret", b"pb_sig_02", hashlib.sha256).hexdigest()
        r = c.post(f"/api/affiliate/postback?tid=pb_sig_02&commission=2.0&network=sovrn&sig={sig}")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        monkeypatch.delenv("POSTBACK_SECRET")


# ── GET /api/revenue ──────────────────────────────────────────────────────────

class TestRevenueEndpoint:
    def test_revenue_returns_required_keys(self, client):
        r = client["client"].get("/api/revenue")
        assert r.status_code == 200
        data = r.json()
        assert "total_commission_usd" in data
        assert "conversion_count" in data
        assert "total_clicks" in data
        assert "epc_usd" in data
        assert "by_network" in data
        assert "daily" in data

    def test_epc_is_zero_with_no_clicks(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = tmp_path
        m.METRICS_FILE = tmp_path / "metrics.json"
        importlib.reload(m)
        # No runs → EPC should be 0 not crash
        assert m.get_total_commission() == 0.0

    def test_daily_list_is_sorted(self, client):
        r = client["client"].get("/api/revenue")
        daily = r.json()["daily"]
        if len(daily) >= 2:
            dates = [d["date"] for d in daily]
            assert dates == sorted(dates)
