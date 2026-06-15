"""Tests for /bio and /links link-in-bio landing page."""

import os
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone


@pytest.fixture(scope="module")
def bio_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("bio_data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ["SPACE_HOST"] = "test.hf.space"

    import importlib
    import api.utils.metrics as mmod
    import api.utils.settings as smod
    mmod.DATA_DIR = data_dir
    mmod.METRICS_FILE = data_dir / "metrics.json"
    smod.DATA_DIR = data_dir
    smod.SETTINGS_FILE = data_dir / "settings.json"
    smod._cache = None
    importlib.reload(mmod)
    importlib.reload(smod)

    # Seed some successful runs
    for i in range(3):
        mmod.record_run({
            "trackingId": f"bio_tid_{i}",
            "success": True,
            "product": f"Test Product {i}",
            "price": 49.99 + i * 10,
            "category": "Electronics",
            "deeplink": f"https://amazon.com/dp/B00{i}",
            "imageUrl": f"https://img.example.com/product{i}.jpg",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    # Seed one failed run (should not appear)
    mmod.record_run({
        "trackingId": "bio_fail",
        "success": False,
        "product": "Failed Product",
        "deeplink": "https://amazon.com/dp/BAD",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield {"client": c, "data_dir": data_dir}

    os.environ.pop("SPACE_HOST", None)


class TestLinkInBioPage:
    def test_bio_route_returns_200(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert r.status_code == 200

    def test_links_route_returns_200(self, bio_client):
        r = bio_client["client"].get("/links")
        assert r.status_code == 200

    def test_returns_html_content_type(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "text/html" in r.headers["content-type"]

    def test_contains_product_names(self, bio_client):
        r = bio_client["client"].get("/bio")
        html = r.text
        assert "Test Product 0" in html
        assert "Test Product 1" in html
        assert "Test Product 2" in html

    def test_does_not_show_failed_runs(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "Failed Product" not in r.text

    def test_contains_tracking_links(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "/r/bio_tid_" in r.text

    def test_contains_price(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "$49.99" in r.text

    def test_contains_category_badge(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "Electronics" in r.text

    def test_contains_shop_now_cta(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "Shop Now" in r.text

    def test_contains_affiliate_disclosure(self, bio_client):
        r = bio_client["client"].get("/bio")
        assert "affiliate" in r.text.lower()

    def test_no_auth_required(self, tmp_path_factory):
        """Bio page must be public — no DASHBOARD_PASSWORD block."""
        data_dir = tmp_path_factory.mktemp("bio_auth_data")
        os.environ["DATA_DIR"] = str(data_dir)
        os.environ["DASHBOARD_PASSWORD"] = "secret"  # pragma: allowlist secret
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = data_dir
        m.METRICS_FILE = data_dir / "metrics.json"
        importlib.reload(m)
        from api.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/bio")
        os.environ.pop("DASHBOARD_PASSWORD", None)
        # Should return 200, not 401
        assert r.status_code == 200

    def test_empty_state_shows_placeholder(self, tmp_path_factory):
        data_dir = tmp_path_factory.mktemp("bio_empty_data")
        os.environ["DATA_DIR"] = str(data_dir)
        os.environ.pop("DASHBOARD_PASSWORD", None)
        import importlib
        import api.utils.metrics as m
        m.DATA_DIR = data_dir
        m.METRICS_FILE = data_dir / "metrics.json"
        importlib.reload(m)
        from api.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/bio")
        assert r.status_code == 200
        assert "check back soon" in r.text.lower() or "no product" in r.text.lower()

    def test_bio_and_links_return_same_content(self, bio_client):
        c = bio_client["client"]
        r1 = c.get("/bio")
        r2 = c.get("/links")
        assert r1.text == r2.text
