"""Browser-based E2E tests for the dashboard UI.

Replaces TestUIStaticAnalysis regex checks with real DOM assertions via
Playwright. The live FastAPI server is started by conftest.py.
"""

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.e2e


class TestDashboardLayout:
    """Sidebar navigation structure is present and correct."""

    def test_page_loads_with_200(self, page: Page, live_server_url):
        response = page.goto(live_server_url, wait_until="domcontentloaded")
        assert response.status == 200

    def test_sidebar_exists(self, page: Page):
        expect(page.locator("#sidebar")).to_be_visible()

    def test_all_nav_items_present(self, page: Page):
        expected = [
            ("nav-overview",  "Overview"),
            ("nav-analytics", "Analytics"),
            ("nav-posts",     "Post History"),
            ("nav-seo",       "SEO"),
            ("nav-ai",        "AI Studio"),
            ("nav-networks",  "Networks"),
            ("nav-schedule",  "Schedule"),
            ("nav-accounts",  "Accounts"),
            ("nav-settings",  "Settings"),
            ("nav-logs",      "Logs"),
        ]
        for nav_id, label in expected:
            locator = page.locator(f"#sidebar #{nav_id}")
            expect(locator).to_be_attached()
            expect(locator.locator(".nav-label")).to_have_text(label)

    def test_overview_page_active_on_load(self, page: Page):
        import re
        expect(page.locator("#page-overview")).to_have_class(re.compile(r"\bactive\b"))

    def test_hamburger_toggle_present(self, page: Page):
        expect(page.locator("#hamburger")).to_be_attached()


class TestNavigation:
    """Clicking nav items switches the visible page."""

    def test_click_settings_shows_settings_page(self, page: Page):
        page.locator("#nav-settings").click()
        expect(page.locator("#page-settings")).to_be_visible()
        expect(page.locator("#page-overview")).not_to_be_visible()

    def test_click_accounts_shows_accounts_page(self, page: Page):
        page.locator("#nav-accounts").click()
        expect(page.locator("#page-accounts")).to_be_visible()

    def test_click_schedule_shows_schedule_page(self, page: Page):
        page.locator("#nav-schedule").click()
        expect(page.locator("#page-schedule")).to_be_visible()

    def test_click_logs_shows_logs_page(self, page: Page):
        page.locator("#nav-logs").click()
        expect(page.locator("#page-logs")).to_be_visible()

    def test_click_back_to_overview(self, page: Page):
        page.locator("#nav-settings").click()
        page.locator("#nav-overview").click()
        expect(page.locator("#page-overview")).to_be_visible()


class TestSettingsForm:
    """Settings page inputs exist and are the correct type."""

    @pytest.fixture(autouse=True)
    def navigate_to_settings(self, page: Page):
        page.locator("#nav-settings").click()

    def test_daily_cost_cap_input_exists(self, page: Page):
        inp = page.locator("#s-cap")
        expect(inp).to_be_attached()
        assert inp.get_attribute("type") == "number"

    def test_alert_threshold_input_exists(self, page: Page):
        expect(page.locator("#s-alert")).to_be_attached()

    def test_max_post_length_input_exists(self, page: Page):
        expect(page.locator("#s-maxlen")).to_be_attached()

    def test_seo_min_score_input_exists(self, page: Page):
        expect(page.locator("#s-seo")).to_be_attached()

    def test_platform_checkboxes_all_present(self, page: Page):
        for pid in ("p-bluesky", "p-mastodon", "p-threads", "p-tumblr",
                    "p-x", "p-facebook", "p-instagram"):
            expect(page.locator(f"#{pid}")).to_be_attached()

    def test_save_button_present(self, page: Page):
        # Must be inside the settings page
        btn = page.locator("#page-settings button").filter(has_text="Save")
        expect(btn).to_be_attached()


class TestActionButtons:
    """Top-bar action buttons are present."""

    def test_run_now_button_present(self, page: Page):
        expect(page.locator("#btn-run")).to_be_attached()

    def test_refresh_button_present(self, page: Page):
        expect(page.locator("#btn-refresh")).to_be_attached()

    def test_diagnose_button_present(self, page: Page):
        expect(page.locator("#btn-diagnose")).to_be_attached()


class TestAPICallsReturnExpectedShapes:
    """Key API calls (via fetch from the page context) return correct shapes."""

    def test_api_health_returns_ok(self, page: Page, live_server_url):
        result = page.evaluate(
            "async (url) => { const r = await fetch(url + '/api/health'); return r.json(); }",
            live_server_url,
        )
        assert result.get("ok") is True

    def test_api_settings_includes_required_keys(self, page: Page, live_server_url):
        result = page.evaluate(
            "async (url) => { const r = await fetch(url + '/api/settings'); return r.json(); }",
            live_server_url,
        )
        for key in ("dailyCostCap", "maxPostLength", "postsPerDay", "schedulerEnabled",
                    "bskyEnabled", "seoMinScore"):
            assert key in result, f"Missing key in /api/settings: {key}"

    def test_api_status_returns_expected_shape(self, page: Page, live_server_url):
        result = page.evaluate(
            "async (url) => { const r = await fetch(url + '/api/status'); return r.json(); }",
            live_server_url,
        )
        for key in ("budget", "circuit_breakers", "pipeline", "runs", "stats"):
            assert key in result, f"Missing key in /api/status: {key}"
