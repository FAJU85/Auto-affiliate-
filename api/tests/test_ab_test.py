"""Tests for A/B caption testing (Build #8)."""

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def ab_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("ab_data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)

    import importlib
    import api.utils.metrics as mmod
    import api.utils.ab_test as abmod
    mmod.DATA_DIR = data_dir
    mmod.METRICS_FILE = data_dir / "metrics.json"
    abmod.DATA_DIR = data_dir
    importlib.reload(mmod)
    importlib.reload(abmod)

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield {"client": c, "data_dir": data_dir, "ab": abmod}

    os.environ.pop("DATA_DIR", None)


# ── assign_variant ─────────────────────────────────────────────────────────────

class TestAssignVariant:
    def test_returns_a_or_b(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        v = ab.assign_variant("track001")
        assert v in ("A", "B")

    def test_same_tracking_id_returns_same_variant(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        v1 = ab.assign_variant("stable_id")
        v2 = ab.assign_variant("stable_id")
        assert v1 == v2

    def test_increments_run_count(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        variant = ab.assign_variant("run_count_test")
        results = ab.get_results()
        assert results["variants"][variant]["runs"] == 1

    def test_multiple_ids_accumulate_runs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        for i in range(10):
            ab.assign_variant(f"id_{i}")
        results = ab.get_results()
        total_runs = sum(v["runs"] for v in results["variants"].values())
        assert total_runs == 10

    def test_over_many_assignments_both_variants_appear(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        variants = {ab.assign_variant(f"v_{i}") for i in range(50)}
        assert "A" in variants
        assert "B" in variants


# ── record_click ───────────────────────────────────────────────────────────────

class TestRecordClick:
    def test_unknown_id_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        result = ab.record_click("nonexistent_id")
        assert result is None

    def test_known_id_returns_variant(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        variant = ab.assign_variant("click_test_01")
        returned = ab.record_click("click_test_01")
        assert returned == variant

    def test_increments_click_count(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        variant = ab.assign_variant("click_count_01")
        ab.record_click("click_count_01")
        ab.record_click("click_count_01")
        results = ab.get_results()
        assert results["variants"][variant]["clicks"] >= 2


# ── get_results ────────────────────────────────────────────────────────────────

class TestGetResults:
    def test_returns_required_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        results = ab.get_results()
        assert "variants" in results
        assert "winner" in results
        assert "total_assignments" in results

    def test_ctr_is_zero_with_no_clicks(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        ab.assign_variant("ctr_zero")
        results = ab.get_results()
        for v_stats in results["variants"].values():
            assert v_stats["ctr"] == 0.0

    def test_ctr_calculated_correctly(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        # Force variant A for 2 IDs (by seeding the data directly)
        data = {"variants": {"A": {"runs": 2, "clicks": 1}, "B": {"runs": 0, "clicks": 0}},
                "assignments": {"id1": {"variant": "A", "assigned_at": 0, "clicks": 1},
                                 "id2": {"variant": "A", "assigned_at": 0, "clicks": 0}}}
        ab._save(data)
        results = ab.get_results()
        assert results["variants"]["A"]["ctr"] == pytest.approx(0.50)

    def test_no_winner_below_10_runs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        for i in range(5):
            ab.assign_variant(f"few_{i}")
        results = ab.get_results()
        assert results["winner"] is None

    def test_winner_declared_with_sufficient_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.ab_test as ab
        ab.DATA_DIR = tmp_path
        importlib.reload(ab)

        # B outperforms A by >5%
        data = {
            "variants": {"A": {"runs": 20, "clicks": 2}, "B": {"runs": 20, "clicks": 8}},
            "assignments": {}
        }
        ab._save(data)
        results = ab.get_results()
        assert results["winner"] == "B"


# ── get_variant_style ──────────────────────────────────────────────────────────

class TestGetVariantStyle:
    def test_variant_a_returns_none(self):
        from api.utils.ab_test import get_variant_style
        assert get_variant_style("A") is None

    def test_variant_b_returns_string(self):
        from api.utils.ab_test import get_variant_style
        style = get_variant_style("B")
        assert isinstance(style, str)
        assert len(style) > 20

    def test_variant_b_mentions_curiosity(self):
        from api.utils.ab_test import get_variant_style
        style = get_variant_style("B")
        assert "curiosity" in style.lower() or "hook" in style.lower() or "social proof" in style.lower()


# ── GET /api/ab-results endpoint ───────────────────────────────────────────────

class TestABResultsEndpoint:
    def test_returns_200(self, ab_client):
        r = ab_client["client"].get("/api/ab-results")
        assert r.status_code == 200

    def test_returns_variants_key(self, ab_client):
        r = ab_client["client"].get("/api/ab-results")
        data = r.json()
        assert "variants" in data

    def test_returns_winner_key(self, ab_client):
        r = ab_client["client"].get("/api/ab-results")
        data = r.json()
        assert "winner" in data

    def test_returns_total_assignments(self, ab_client):
        r = ab_client["client"].get("/api/ab-results")
        data = r.json()
        assert "total_assignments" in data
