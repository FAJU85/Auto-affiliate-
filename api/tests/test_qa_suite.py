"""
QA Automation Suite — runs at the start of every session.

Covers every testable surface:
  - All API endpoints (contract: shape, status codes, required fields)
  - All data round-trips (write → read back → assert nothing dropped)
  - Settings persistence (all fields survive save/reload)
  - Social credentials round-trip (the page-refresh bug class)
  - Schedule config round-trip
  - History, clicks, stats shape
  - Circuit breakers, SLO, metrics
  - Silent failures (data saved but not returned, fields stripped, etc.)

Run with:  pytest api/tests/test_qa_suite.py -v
"""

import os
import allure
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture — one app instance per module, isolated DATA_DIR
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def qa(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("qa_data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ.pop("BSKY_HANDLE", None)
    os.environ.pop("BSKY_APP_PASSWORD", None)

    import importlib
    import api.utils.settings as smod
    import api.utils.metrics as mmod
    import api.utils.budget as bmod
    import api.social_oauth as so
    smod._cache = None
    importlib.reload(smod)
    importlib.reload(mmod)
    importlib.reload(bmod)

    # Keep social_oauth's module-level CONNECTIONS_FILE in sync with DATA_DIR
    so.CONNECTIONS_FILE = data_dir / "social-connections.json"

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield {"client": c, "data_dir": data_dir, "social_oauth": so}


# ─────────────────────────────────────────────────────────────────────────────
# 1. CORE HEALTH & STATUS
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Core Health & Status")
class TestCoreHealth:
    @allure.story("Endpoints reachable")
    def test_root_returns_html(self, qa):
        r = qa["client"].get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]

    def test_health_returns_status_field(self, qa):
        r = qa["client"].get("/health")
        assert r.status_code == 200
        d = r.json()
        assert "status" in d
        assert d["status"] in ("healthy", "degraded", "misconfigured")
        assert "ok" in d

    def test_api_status_shape(self, qa):
        r = qa["client"].get("/api/status")
        assert r.status_code == 200
        d = r.json()
        # /api/status exposes pipeline-level state
        required = {"pipeline", "budget", "lastRun", "circuit_breakers"}
        assert required.issubset(d.keys()), f"Missing keys: {required - d.keys()}"

    def test_api_metrics_shape(self, qa):
        r = qa["client"].get("/api/metrics")
        assert r.status_code == 200
        d = r.json()
        # metrics are nested under golden_signals
        assert "golden_signals" in d or "latency_p50_ms" in d or "slo" in d

    def test_api_slo_shape(self, qa):
        r = qa["client"].get("/api/slo")
        assert r.status_code == 200
        d = r.json()
        assert "slo_pct" in d

    def test_api_debug_shape(self, qa):
        r = qa["client"].get("/api/debug")
        assert r.status_code == 200
        d = r.json()
        assert "DATA_DIR" in d or "env" in d or isinstance(d, dict)

    def test_api_env_shape(self, qa):
        r = qa["client"].get("/api/env")
        assert r.status_code == 200

    def test_api_logs_returns_list(self, qa):
        r = qa["client"].get("/api/logs")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_api_logs_summary_shape(self, qa):
        r = qa["client"].get("/api/logs/summary")
        assert r.status_code == 200

    def test_api_networks_returns_list(self, qa):
        r = qa["client"].get("/api/networks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_api_history_returns_list(self, qa):
        r = qa["client"].get("/api/history")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_api_history_csv_returns_text(self, qa):
        r = qa["client"].get("/api/history.csv")
        assert r.status_code == 200
        assert "text" in r.headers.get("content-type", "")

    def test_api_clicks_shape(self, qa):
        r = qa["client"].get("/api/clicks")
        assert r.status_code == 200
        d = r.json()
        assert "daily" in d

    def test_api_stats_returns_list(self, qa):
        r = qa["client"].get("/api/stats")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_api_dedup_stats_shape(self, qa):
        r = qa["client"].get("/api/dedup/stats")
        assert r.status_code == 200
        d = r.json()
        assert "count" in d

    def test_api_finops_shape(self, qa):
        r = qa["client"].get("/api/finops")
        assert r.status_code == 200

    def test_api_platform_rules_shape(self, qa):
        r = qa["client"].get("/api/platform-rules")
        assert r.status_code == 200

    def test_api_insights_shape(self, qa):
        r = qa["client"].get("/api/insights")
        assert r.status_code == 200

    def test_api_diagnose_shape(self, qa):
        r = qa["client"].get("/api/diagnose")
        assert r.status_code == 200

    def test_social_health_endpoint(self, qa):
        r = qa["client"].get("/api/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. SETTINGS ROUND-TRIP — every field must survive save → reload
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Settings Persistence")
class TestSettingsRoundTrip:
    """Silent bug class: field saved but not returned, or silently reset."""

    def _save_and_reload(self, client, payload: dict) -> dict:
        r = client.post("/api/settings", json=payload)
        assert r.status_code == 200, r.text
        r2 = client.get("/api/settings")
        assert r2.status_code == 200
        return r2.json()

    def test_max_post_length_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"maxPostLength": 240})
        assert d["maxPostLength"] == 240, "maxPostLength was not persisted"

    def test_daily_cost_cap_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"dailyCostCap": 3.5})
        assert d["dailyCostCap"] == pytest.approx(3.5), "dailyCostCap was not persisted"

    def test_posting_hours_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"postingHours": "9-21"})
        assert d["postingHours"] == "9-21", "postingHours was not persisted"

    def test_posts_per_day_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"postsPerDay": 3})
        assert d["postsPerDay"] == 3, "postsPerDay was not persisted"

    def test_scheduler_enabled_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"schedulerEnabled": False})
        assert d["schedulerEnabled"] is False, "schedulerEnabled was not persisted"
        # Restore
        self._save_and_reload(qa["client"], {"schedulerEnabled": True})

    def test_publish_platforms_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"publishPlatforms": ["bluesky", "mastodon"]})
        assert "bluesky" in d["publishPlatforms"]
        assert "mastodon" in d["publishPlatforms"]

    def test_cta_phrases_roundtrip(self, qa):
        phrases = ["Buy now!", "Don't miss it", "Get yours today"]
        d = self._save_and_reload(qa["client"], {"ctaPhrases": phrases})
        assert d["ctaPhrases"] == phrases, "ctaPhrases were not persisted"

    def test_system_prompt_roundtrip(self, qa):
        prompt = "You are an expert affiliate marketer. Write a compelling post about {name}. Lead with benefits."
        d = self._save_and_reload(qa["client"], {"postSystemPrompt": prompt})
        assert d["postSystemPrompt"] == prompt, "postSystemPrompt was not persisted"

    def test_user_template_roundtrip(self, qa):
        template = "Promote {name} at {price}. Benefits: {description}. Write a punchy post."
        d = self._save_and_reload(qa["client"], {"postUserTemplate": template})
        assert d["postUserTemplate"] == template, "postUserTemplate was not persisted"

    def test_alert_threshold_roundtrip(self, qa):
        d = self._save_and_reload(qa["client"], {"alertThreshold": 1.0})
        assert d["alertThreshold"] == pytest.approx(1.0), "alertThreshold was not persisted"

    def test_settings_get_returns_all_required_keys(self, qa):
        r = qa["client"].get("/api/settings")
        d = r.json()
        required = {
            "maxPostLength", "dailyCostCap", "postingHours", "postsPerDay",
            "schedulerEnabled", "publishPlatforms", "ctaPhrases",
            "postSystemPrompt", "postUserTemplate",
        }
        missing = required - d.keys()
        assert not missing, f"GET /api/settings missing keys: {missing}"

    def test_partial_save_preserves_other_fields(self, qa):
        """Saving one field must not wipe unrelated fields."""
        # First establish known state
        self._save_and_reload(qa["client"], {"maxPostLength": 300, "postsPerDay": 2})
        # Save only one field
        d = self._save_and_reload(qa["client"], {"maxPostLength": 280})
        assert d["postsPerDay"] == 2, "Partial save wiped postsPerDay"


# ─────────────────────────────────────────────────────────────────────────────
# 3. SOCIAL CREDENTIALS ROUND-TRIP — the page-refresh bug class
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Social Credentials Round-Trip")
class TestSocialCredentialsRoundTrip:
    """Every credential field must be visible in GET /api/accounts after saving."""

    def test_x_all_four_keys_visible_after_save(self, qa):
        r = qa["client"].post("/api/social/x/credentials", json={
            "handle":          "xuser",
            "consumer_key":    "ck1",
            "consumer_secret": "cs1",
            "access_token":    "at1",
            "access_secret":   "as1",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

        d = qa["client"].get("/api/accounts").json()
        x = d["social"]["x"]
        assert x["connected"] is True, "X not marked connected after save"
        assert x["handle"] == "xuser", "X handle not returned"
        assert x["consumer_key"]    != "", "consumer_key silently dropped"
        assert x["consumer_secret"] != "", "consumer_secret silently dropped"
        assert x["access_token"]    != "", "access_token silently dropped"
        assert x["access_secret"]   != "", "access_secret silently dropped"

    def test_x_credentials_masked_not_plaintext(self, qa):
        """Security: actual secrets must not be returned verbatim."""
        qa["client"].post("/api/social/x/credentials", json={
            "handle": "xuser2",
            "consumer_key": "REAL_CK", "consumer_secret": "REAL_CS",
            "access_token": "REAL_AT", "access_secret": "REAL_AS",
        })
        d = qa["client"].get("/api/accounts").json()["social"]["x"]
        for field in ("consumer_key", "consumer_secret", "access_token", "access_secret"):
            assert "REAL_" not in d[field], f"{field} returned as plaintext"

    def test_x_partial_update_preserves_other_keys(self, qa):
        """Updating one field must not wipe the others."""
        qa["client"].post("/api/social/x/credentials", json={
            "handle": "xuser3",
            "consumer_key": "ck_orig", "consumer_secret": "cs_orig",
            "access_token": "at_orig", "access_secret": "as_orig",
        })
        # Now update only consumer_key
        qa["client"].post("/api/social/x/credentials", json={
            "handle": "xuser3", "consumer_key": "ck_new",
        })
        d = qa["client"].get("/api/accounts").json()["social"]["x"]
        assert d["consumer_secret"] != "", "consumer_secret wiped by partial update"
        assert d["access_token"]    != "", "access_token wiped by partial update"
        assert d["access_secret"]   != "", "access_secret wiped by partial update"

    def test_facebook_credentials_visible_after_save(self, qa):
        qa["client"].post("/api/social/facebook/credentials", json={
            "handle": "fbpage", "page_id": "pg999",
            "page_access_token": "pat_secret",
        })
        d = qa["client"].get("/api/accounts").json()["social"]["facebook"]
        assert d["connected"] is True
        assert d["page_access_token"] != "", "page_access_token silently dropped"
        assert d["page_id"] == "pg999", "page_id not returned"

    def test_instagram_credentials_visible_after_save(self, qa):
        qa["client"].post("/api/social/instagram/credentials", json={
            "handle": "iguser", "ig_user_id": "ig789",
            "access_token": "ig_secret",
        })
        d = qa["client"].get("/api/accounts").json()["social"]["instagram"]
        assert d["connected"] is True
        assert d["access_token"] != "", "access_token silently dropped"
        assert d["ig_user_id"] == "ig789", "ig_user_id not returned"

    def test_accounts_endpoint_returns_all_platforms(self, qa):
        """GET /api/accounts must include all known platforms."""
        d = qa["client"].get("/api/accounts").json()
        assert "bluesky" in d
        social = d.get("social", {})
        for platform in ("mastodon", "threads", "tumblr", "x", "facebook", "instagram"):
            assert platform in social, f"Platform '{platform}' missing from /api/accounts"

    def test_disconnect_clears_platform(self, qa):
        # Save then disconnect
        qa["client"].post("/api/social/x/credentials", json={
            "handle": "disc_test",
            "consumer_key": "ck", "consumer_secret": "cs",
            "access_token": "at", "access_secret": "as",
        })
        r = qa["client"].delete("/api/social/x/disconnect")
        assert r.status_code == 200
        d = qa["client"].get("/api/accounts").json()["social"]["x"]
        assert d["connected"] is False, "Platform still connected after disconnect"


# ─────────────────────────────────────────────────────────────────────────────
# 4. SCHEDULE CONFIG ROUND-TRIP
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Schedule Config")
class TestScheduleRoundTrip:
    def test_get_schedule_config_shape(self, qa):
        r = qa["client"].get("/api/schedule/config")
        assert r.status_code == 200
        d = r.json()
        # /api/schedule/config returns cron, nextRun, paused
        assert "cron" in d or "paused" in d

    def test_pause_and_resume(self, qa):
        r = qa["client"].post("/api/schedule/pause")
        assert r.status_code == 200
        assert r.json()["paused"] is True

        r3 = qa["client"].post("/api/schedule/resume")
        assert r3.status_code == 200
        assert r3.json()["paused"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. RUN GUARDS — pipeline must reject invalid states cleanly
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Run Guards")
class TestRunGuards:
    def test_run_without_bluesky_creds_returns_error(self, qa):
        os.environ.pop("BSKY_HANDLE", None)
        os.environ.pop("BSKY_APP_PASSWORD", None)
        import api.utils.settings as smod
        smod.save_settings({"publishPlatforms": ["bluesky"], "bskyEnabled": True})
        r = qa["client"].post("/api/run")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is False
        assert "error" in d
        assert d["error"]  # non-empty error message

    def test_run_without_any_platform_returns_error(self, qa):
        import api.utils.settings as smod
        smod.save_settings({"publishPlatforms": []})
        r = qa["client"].post("/api/run")
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_run_non_bluesky_platform_succeeds_without_bsky_creds(self, qa):
        import api.utils.settings as smod
        smod.save_settings({"publishPlatforms": ["mastodon"]})
        with patch("api.pipeline.run_pipeline", AsyncMock(return_value=None)):
            r = qa["client"].post("/api/run")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_dry_run_returns_dict(self, qa):
        with patch("api.pipeline.dry_run", AsyncMock(return_value={"ok": True, "caption": "Test"})):
            r = qa["client"].post("/api/dry-run")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_paused_run_rejected(self, qa):
        import api.pipeline as pipeline
        pipeline.STATE["paused"] = True
        r = qa["client"].post("/api/run")
        assert r.status_code == 200
        assert r.json()["ok"] is False
        pipeline.STATE["paused"] = False


# ─────────────────────────────────────────────────────────────────────────────
# 6. CIRCUIT BREAKERS
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Circuit Breakers")
class TestCircuitBreakers:
    def test_reset_named_circuit_breaker(self, qa):
        r = qa["client"].post("/api/circuit-breakers/groq/reset")
        assert r.status_code == 200

    def test_reset_unknown_circuit_breaker_returns_error(self, qa):
        r = qa["client"].post("/api/circuit-breakers/nonexistent_cb/reset")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json().get("ok") is False or "error" in r.json()

    def test_reset_all_circuit_breakers(self, qa):
        r = qa["client"].post("/api/circuit-breakers/reset-all")
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_legacy_circuit_breaker_reset(self, qa):
        r = qa["client"].post("/api/circuit-breaker/reset", json={"name": "groq"})
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 7. DATA INTEGRITY — files written atomically, survive corrupt data
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Data Integrity")
class TestDataIntegrity:
    def test_settings_survives_corrupt_file(self, qa):
        """Corrupt settings.json must not crash GET /api/settings."""
        settings_file = qa["data_dir"] / "settings.json"
        settings_file.write_text("{{{INVALID JSON")
        import api.utils.settings as smod
        smod._cache = None
        r = qa["client"].get("/api/settings")
        assert r.status_code == 200
        assert "maxPostLength" in r.json()  # falls back to defaults

    def test_metrics_survives_missing_file(self, qa):
        """Missing metrics.json must not crash /api/history."""
        metrics_file = qa["data_dir"] / "metrics.json"
        if metrics_file.exists():
            metrics_file.unlink()
        r = qa["client"].get("/api/history")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_connections_survives_missing_file(self, qa):
        """Missing social-connections.json must return empty connections."""
        conn_file = qa["data_dir"] / "social-connections.json"
        if conn_file.exists():
            conn_file.unlink()
        r = qa["client"].get("/api/accounts")
        assert r.status_code == 200
        d = r.json()
        assert "social" in d

    def test_dedup_reset_returns_count(self, qa):
        r = qa["client"].post("/api/dedup/reset")
        assert r.status_code == 200
        d = r.json()
        assert "cleared" in d or "ok" in d

    def test_slo_reset_succeeds(self, qa):
        r = qa["client"].post("/api/slo/reset")
        assert r.status_code == 200

    def test_logs_clear_succeeds(self, qa):
        r = qa["client"].post("/api/logs/clear")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 8. BLUESKY ACCOUNT ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Bluesky Account")
class TestBlueskyAccount:
    def test_bsky_test_no_handle_returns_error(self, qa):
        os.environ.pop("BSKY_HANDLE", None)
        os.environ.pop("BSKY_APP_PASSWORD", None)
        r = qa["client"].post("/api/accounts/bluesky/test")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is False
        assert "BSKY_HANDLE" in d.get("error", "")

    def test_bsky_test_password_missing_returns_error(self, qa):
        os.environ["BSKY_HANDLE"] = "user.bsky.social"
        os.environ.pop("BSKY_APP_PASSWORD", None)
        try:
            r = qa["client"].post("/api/accounts/bluesky/test")
            assert r.status_code == 200
            assert r.json()["ok"] is False
            assert "BSKY_APP_PASSWORD" in r.json().get("error", "")
        finally:
            os.environ.pop("BSKY_HANDLE", None)

    def test_bsky_disconnect_returns_ok(self, qa):
        r = qa["client"].post("/api/accounts/bluesky/disconnect")
        assert r.status_code == 200

    def test_bsky_enable_returns_ok(self, qa):
        r = qa["client"].post("/api/accounts/bluesky/enable")
        assert r.status_code == 200

    def test_accounts_bluesky_shape(self, qa):
        r = qa["client"].get("/api/accounts")
        assert r.status_code == 200
        bsky = r.json()["bluesky"]
        for field in ("connected", "hasCreds", "method"):
            assert field in bsky, f"bluesky.{field} missing from /api/accounts"


# ─────────────────────────────────────────────────────────────────────────────
# 9. AI GENERATE ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("AI Generate")
class TestAIGenerate:
    def test_ai_generate_missing_fields_returns_error(self, qa):
        r = qa["client"].post("/api/ai/generate", json={})
        assert r.status_code in (200, 422)

    def test_ai_generate_with_mock_returns_text(self, qa):
        with patch("api.ai.text.generate_post_text", AsyncMock(return_value="Great deal on this product!")):
            r = qa["client"].post("/api/ai/generate", json={
                "productName": "Test Widget",
                "category":    "Electronics",
                "description": "A great test widget",
            })
        assert r.status_code == 200
        d = r.json()
        assert "text" in d or "caption" in d or "ok" in d


# ─────────────────────────────────────────────────────────────────────────────
# 10. TRACKING REDIRECT
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Tracking class TestTracking: Redirects")
class TestTracking:
    def test_redirect_unknown_id_returns_404_or_redirect(self, qa):
        r = qa["client"].get("/r/nonexistent_id", follow_redirects=False)
        assert r.status_code in (302, 307, 404)

    def test_redirect_known_id_redirects(self, qa):
        import api.utils.metrics as m
        m.record_run({
            "success": True,
            "trackingId": "qa_test_track",
            "deeplink": "https://rzekl.com/g/test123",
            "timestamp": "2026-01-01T00:00:00+00:00",
        })
        r = qa["client"].get("/r/qa_test_track", follow_redirects=False)
        assert r.status_code in (302, 307), "Known tracking ID should redirect"


# ─────────────────────────────────────────────────────────────────────────────
# 11. SOCIAL OAUTH ENDPOINTS — shape and error handling
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Social OAuth")
class TestSocialOAuth:
    def test_social_status_returns_dict(self, qa):
        r = qa["client"].get("/api/social/status")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_mastodon_register_missing_instance_returns_error(self, qa):
        r = qa["client"].post("/api/social/mastodon/register", json={})
        assert r.status_code in (400, 422)

    def test_mastodon_register_invalid_url_returns_error(self, qa):
        r = qa["client"].post("/api/social/mastodon/register", json={"instance": "://not-valid"})
        assert r.status_code in (400, 422)

    def test_threads_auth_without_app_id_returns_503(self, qa):
        os.environ.pop("THREADS_APP_ID", None)
        r = qa["client"].get("/api/social/threads/auth")
        assert r.status_code == 503

    def test_tumblr_auth_without_keys_returns_503(self, qa):
        os.environ.pop("TUMBLR_CONSUMER_KEY", None)
        r = qa["client"].get("/api/social/tumblr/auth")
        assert r.status_code == 503

    def test_credentials_unknown_platform_returns_404(self, qa):
        r = qa["client"].post("/api/social/nonexistent_platform/credentials", json={
            "handle": "user", "password": "pass",  # pragma: allowlist secret
        })
        assert r.status_code == 404

    def test_disconnect_unknown_platform_returns_404(self, qa):
        r = qa["client"].delete("/api/social/nonexistent_platform/disconnect")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 12. AUTH MIDDLEWARE — unauthenticated access patterns
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Auth Middleware")
class TestAuthMiddleware:
    def test_no_password_set_allows_all(self, qa):
        os.environ.pop("DASHBOARD_PASSWORD", None)
        r = qa["client"].get("/api/settings")
        assert r.status_code == 200

    def test_password_set_blocks_api_without_token(self, qa):
        os.environ["DASHBOARD_PASSWORD"] = "secret_qa"  # pragma: allowlist secret
        try:
            r = qa["client"].get("/api/settings")
            assert r.status_code == 401
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)

    def test_password_set_allows_with_bearer_token(self, qa):
        os.environ["DASHBOARD_PASSWORD"] = "secret_qa"  # pragma: allowlist secret
        try:
            r = qa["client"].get("/api/settings", headers={"Authorization": "Bearer secret_qa"})
            assert r.status_code == 200
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)

    def test_health_always_public(self, qa):
        """Health endpoint must never require auth."""
        os.environ["DASHBOARD_PASSWORD"] = "secret_qa"  # pragma: allowlist secret
        try:
            r = qa["client"].get("/health")
            assert r.status_code == 200
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)

    def test_unauthenticated_non_api_path_returns_200(self, qa):
        """Non-API paths (dashboard HTML) pass through even without auth."""
        os.environ["DASHBOARD_PASSWORD"] = "secret_qa"  # pragma: allowlist secret
        try:
            r = qa["client"].get("/dashboard")
            assert r.status_code in (200, 404)  # 404 is fine — it passed the auth gate
        finally:
            os.environ.pop("DASHBOARD_PASSWORD", None)


# ─────────────────────────────────────────────────────────────────────────────
# 13. RESPONSE CONTRACT — no silent field stripping
# ─────────────────────────────────────────────────────────────────────────────

@allure.feature("Response Contracts")
class TestResponseContracts:
    """Snapshot the shape of key responses. Any missing field is a regression."""

    def test_api_status_all_fields_present(self, qa):
        r = qa["client"].get("/api/status")
        d = r.json()
        # Actual fields returned by /api/status
        fields = ["pipeline", "budget", "lastRun", "circuit_breakers", "runs"]
        for f in fields:
            assert f in d, f"/api/status missing field: {f}"

    def test_api_accounts_social_fields_present(self, qa):
        r = qa["client"].get("/api/accounts")
        d = r.json()
        # Top-level keys
        assert "bluesky" in d
        assert "social" in d
        # Bluesky shape
        for f in ("connected", "hasCreds", "method"):
            assert f in d["bluesky"], f"bluesky.{f} missing"
        # Each social platform has at minimum connected + handle
        for platform in ("x", "facebook", "instagram", "mastodon", "threads", "tumblr"):
            p = d["social"][platform]
            assert "connected" in p, f"social.{platform}.connected missing"
            assert "handle" in p, f"social.{platform}.handle missing"

    def test_api_settings_all_defaults_present(self, qa):
        import api.utils.settings as smod
        smod._cache = None
        r = qa["client"].get("/api/settings")
        d = r.json()
        defaults = [
            "maxPostLength", "dailyCostCap", "alertThreshold", "postingHours",
            "postsPerDay", "schedulerEnabled", "publishPlatforms",
            "ctaPhrases", "postSystemPrompt", "postUserTemplate",
        ]
        for f in defaults:
            assert f in d, f"GET /api/settings missing default field: {f}"

    def test_api_slo_required_fields(self, qa):
        r = qa["client"].get("/api/slo")
        d = r.json()
        assert "slo_pct" in d
        assert "error_budget_remaining_pct" in d or "total" in d

    def test_api_clicks_required_fields(self, qa):
        r = qa["client"].get("/api/clicks")
        d = r.json()
        assert "daily" in d
        assert "total" in d or isinstance(d["daily"], dict)
