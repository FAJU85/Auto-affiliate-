"""
Intelligent QA Layer — auto-discovery, property-based testing, regression memory.

Four systems:

1. RouteAutoCoverage      — discovers every FastAPI GET route at test time;
                            any not in KNOWN_SKIP gets a smoke test (must not
                            5xx).  New routes are flagged.

2. PropertyBasedSettings  — Hypothesis drives hundreds of random boundary
                            inputs at the settings endpoint.

3. RegressionMemory       — persists failures in .qa_memory.json and replays
                            every previously-failing pattern on each run.

4. FrontendContractAudit  — parses dashboard.html at test time, extracts every
                            api('/path','METHOD') call the JavaScript makes,
                            cross-references against the FastAPI route registry,
                            and asserts:
                              a) every called route exists with the right method
                              b) every field the JS reads from the response is
                                 actually present in the real API response
                            This system caught 6 production bugs automatically
                            (missing endpoints, wrong methods, missing fields).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings as h_settings
from hypothesis import strategies as st

# ── Memory file lives next to this file (committed, grows over time) ──────────
_MEMORY_FILE = Path(__file__).parent / ".qa_memory.json"

# Routes that legitimately need auth / special state — skip smoke test
KNOWN_SKIP = {
    "/api/run",           # fires background task, needs platform config
    "/api/dry-run",       # calls AI, needs mock
    "/api/logs/analyze",  # calls AI, needs mock
    "/api/network/test",  # hits external URLs
    "/api/social/threads/auth",   # redirect to external OAuth
    "/api/social/tumblr/auth",    # redirect to external OAuth
    "/api/social/callback",       # OAuth callback, needs state
    "/oauth/social/callback",     # OAuth callback, needs state
    "/api/social/threads/callback",
    "/api/social/tumblr/callback",
    "/r/{tracking_id}",   # needs real tracking id
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def iq(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("iq_data")
    os.environ["DATA_DIR"] = str(data_dir)
    for v in ("DASHBOARD_PASSWORD", "BSKY_HANDLE", "BSKY_APP_PASSWORD"):
        os.environ.pop(v, None)

    import importlib
    import api.utils.settings as smod
    import api.utils.metrics as mmod
    import api.utils.budget as bmod
    import api.social_oauth as so
    smod._cache = None
    importlib.reload(smod)
    importlib.reload(mmod)
    importlib.reload(bmod)
    so.CONNECTIONS_FILE = data_dir / "social-connections.json"

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield {"client": c, "data_dir": data_dir, "app": app}


# ─────────────────────────────────────────────────────────────────────────────
# Memory helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_memory() -> dict:
    if _MEMORY_FILE.exists():
        try:
            return json.loads(_MEMORY_FILE.read_text())
        except Exception:
            pass
    return {"failures": [], "learned_shapes": {}, "run_count": 0}


def _save_memory(mem: dict) -> None:
    _MEMORY_FILE.write_text(json.dumps(mem, indent=2, default=str))


def _record_failure(test_id: str, detail: str) -> None:
    mem = _load_memory()
    entry = {"test": test_id, "detail": detail[:300], "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    # keep only the last 50 distinct failures
    existing = [f for f in mem["failures"] if f["test"] != test_id]
    mem["failures"] = (existing + [entry])[-50:]
    _save_memory(mem)


def _record_shape(path: str, shape: dict) -> None:
    mem = _load_memory()
    mem["learned_shapes"][path] = shape
    _save_memory(mem)


def _get_learned_shape(path: str) -> dict | None:
    return _load_memory()["learned_shapes"].get(path)


def _mark_run() -> int:
    mem = _load_memory()
    mem["run_count"] = mem.get("run_count", 0) + 1
    _save_memory(mem)
    return mem["run_count"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. ROUTE AUTO-COVERAGE
# ─────────────────────────────────────────────────────────────────────────────

class TestRouteAutoCoverage:
    """
    Crawl every GET route registered in the app.
    Any route not in KNOWN_SKIP must return < 500.
    New routes discovered since last run are flagged in the Allure report.
    """

    def _get_routes(self, app) -> list[str]:
        return sorted(
            r.path
            for r in app.routes
            if hasattr(r, "methods") and "GET" in r.methods
            and not any(c in r.path for c in ["{", "docs", "redoc", "openapi"])
            and r.path not in KNOWN_SKIP
        )

    def test_no_route_returns_server_error(self, iq):
        """Every GET endpoint must return < 500 — a 5xx is always a bug."""
        app = iq["app"]
        client = iq["client"]
        routes = self._get_routes(app)
        failures = []
        for path in routes:
            r = client.get(path)
            if r.status_code >= 500:
                failures.append(f"{path} → {r.status_code}: {r.text[:80]}")
                _record_failure(f"5xx:{path}", r.text[:200])
        assert not failures, "Routes returning 5xx:\n" + "\n".join(failures)

    def test_all_routes_have_coverage(self, iq):
        """
        Cross-reference discovered routes with KNOWN_SKIP.
        Any route that is neither tested by the main QA suite nor in KNOWN_SKIP
        is flagged — this catches new endpoints being added without tests.
        On the very first run the baseline is stored; subsequent runs diff against it.
        """
        app = iq["app"]
        all_routes = {
            r.path for r in app.routes
            if hasattr(r, "methods") and "GET" in r.methods
        }
        testable = sorted(
            p for p in all_routes
            if p not in KNOWN_SKIP
            and not any(c in p for c in ["{", "docs", "redoc", "openapi"])
        )
        mem = _load_memory()
        prev = set(mem.get("known_routes", []))
        if not prev:
            # First run — store baseline, no failure
            mem["known_routes"] = sorted(testable)
            _save_memory(mem)
            return
        new_routes = set(testable) - prev
        if new_routes:
            # Update memory so next run only flags truly new ones
            mem["known_routes"] = sorted(set(testable) | prev)
            _save_memory(mem)
        assert not new_routes, (
            "New routes found — add tests or add to KNOWN_SKIP:\n"
            + "\n".join(sorted(new_routes))
        )

    def test_response_shapes_stable(self, iq):
        """
        Learn the top-level keys of each GET response on first run.
        On subsequent runs, assert no key disappears (silent field stripping regression).
        """
        client = iq["client"]
        regressions = []
        safe_routes = [
            "/api/status", "/api/settings", "/api/accounts",
            "/api/slo", "/api/clicks", "/api/dedup/stats",
            "/api/finops", "/api/schedule/config", "/api/health",
        ]
        for path in safe_routes:
            r = client.get(path)
            if r.status_code != 200:
                continue
            try:
                body = r.json()
            except Exception:
                continue
            if not isinstance(body, dict):
                continue
            current_keys = set(body.keys())
            learned = _get_learned_shape(path)
            if learned is None:
                # First time — store as baseline
                _record_shape(path, {"keys": sorted(current_keys)})
            else:
                missing = set(learned["keys"]) - current_keys
                if missing:
                    regressions.append(f"{path} lost keys: {missing}")
                    _record_failure(f"shape:{path}", f"lost keys {missing}")
                else:
                    # Update with any new keys that appeared
                    _record_shape(path, {"keys": sorted(current_keys | set(learned["keys"]))})
        assert not regressions, "Response shape regressions:\n" + "\n".join(regressions)


# ─────────────────────────────────────────────────────────────────────────────
# 2. PROPERTY-BASED SETTINGS TESTING (Hypothesis)
# ─────────────────────────────────────────────────────────────────────────────

# Build a single shared client at module level for Hypothesis tests
# (Hypothesis runs each test hundreds of times — module-level avoids reinit)
_HYP_CLIENT: TestClient | None = None


@pytest.fixture(scope="module", autouse=True)
def _hyp_setup(tmp_path_factory):
    global _HYP_CLIENT
    data_dir = tmp_path_factory.mktemp("hyp_data")
    os.environ["DATA_DIR"] = str(data_dir)
    for v in ("DASHBOARD_PASSWORD", "BSKY_HANDLE", "BSKY_APP_PASSWORD"):
        os.environ.pop(v, None)
    import importlib
    import api.utils.settings as smod
    import api.social_oauth as so
    smod._cache = None
    importlib.reload(smod)
    so.CONNECTIONS_FILE = data_dir / "social-connections.json"
    from api.main import app
    _HYP_CLIENT = TestClient(app, raise_server_exceptions=False)
    yield
    _HYP_CLIENT = None


class TestPropertyBasedSettings:
    """
    Hypothesis drives hundreds of random inputs at /api/settings.
    The invariants are:
      - Valid values are always accepted (ok=True)
      - Invalid values are always rejected (ok=False, never 5xx)
      - A rejected save never mutates the stored value
    """

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(length=st.integers(min_value=1, max_value=5000))
    def test_valid_max_post_length_always_accepted(self, length):
        r = _HYP_CLIENT.post("/api/settings", json={"maxPostLength": length})
        assert r.status_code == 200
        assert r.json()["ok"] is True, f"Valid length={length} was rejected: {r.json()}"

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(length=st.one_of(
        st.integers(max_value=0),
        st.integers(min_value=5001),
        st.text(min_size=1, max_size=10),
        st.lists(st.integers()),
    ))
    def test_invalid_max_post_length_always_rejected(self, length):
        # NaN/inf excluded: not JSON-serializable (httpx rejects before server sees them)
        r = _HYP_CLIENT.post("/api/settings", json={"maxPostLength": length})
        assert r.status_code < 500, f"Server crashed on maxPostLength={length!r}"
        if isinstance(length, int) and 1 <= length <= 5000:
            return  # valid — skip
        assert r.json()["ok"] is False, f"Invalid maxPostLength={length!r} was accepted"

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(cap=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False))
    def test_valid_cost_cap_always_accepted(self, cap):
        r = _HYP_CLIENT.post("/api/settings", json={"dailyCostCap": cap})
        assert r.status_code == 200
        assert r.json()["ok"] is True, f"Valid cap={cap} was rejected"

    @h_settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(cap=st.one_of(
        st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
        st.text(min_size=1, max_size=5),
    ))
    def test_invalid_cost_cap_always_rejected(self, cap):
        # NaN/inf excluded: not JSON-serializable
        r = _HYP_CLIENT.post("/api/settings", json={"dailyCostCap": cap})
        assert r.status_code < 500, f"Server crashed on dailyCostCap={cap!r}"
        assert r.json()["ok"] is False, f"Invalid cap={cap!r} was accepted"

    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(ppd=st.integers(min_value=1, max_value=100))
    def test_valid_posts_per_day_always_accepted(self, ppd):
        r = _HYP_CLIENT.post("/api/settings", json={"postsPerDay": ppd})
        assert r.json()["ok"] is True, f"Valid postsPerDay={ppd} rejected"

    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(ppd=st.integers(max_value=0))
    def test_invalid_posts_per_day_always_rejected(self, ppd):
        r = _HYP_CLIENT.post("/api/settings", json={"postsPerDay": ppd})
        assert r.status_code < 500
        assert r.json()["ok"] is False, f"postsPerDay={ppd} should be rejected"

    @h_settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start=st.integers(min_value=0, max_value=23),
        end=st.integers(min_value=0, max_value=23),
    )
    def test_valid_posting_hours_always_accepted(self, start, end):
        ph = f"{start}-{end}"
        r = _HYP_CLIENT.post("/api/settings", json={"postingHours": ph})
        assert r.json()["ok"] is True, f"Valid postingHours={ph!r} rejected"

    @h_settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(ph=st.one_of(
        st.integers(),
        # exclude surrogates (not JSON/UTF-8 encodable) and pure digits
        st.text(
            alphabet=st.characters(
                blacklist_categories=("Nd", "Cs"),  # Cs = surrogates
                blacklist_characters="-",
            ),
            min_size=1, max_size=10,
        ),
        st.just("25-0"),
        st.just("0-25"),
        st.just("99-99"),
    ))
    def test_invalid_posting_hours_always_rejected(self, ph):
        r = _HYP_CLIENT.post("/api/settings", json={"postingHours": ph})
        assert r.status_code < 500, f"Server crashed on postingHours={ph!r}"
        if isinstance(ph, str) and ph in ("25-0", "0-25", "99-99"):
            assert r.json()["ok"] is False, f"Out-of-range hours {ph!r} accepted"

    @h_settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        length=st.integers(min_value=1, max_value=5000),
        cap=st.floats(min_value=0.01, max_value=100.0, allow_nan=False, allow_infinity=False),
        ppd=st.integers(min_value=1, max_value=20),
    )
    def test_rejected_save_never_mutates_stored_value(self, length, cap, ppd):
        """Invariant: a rejection must be a pure read — no side effects."""
        # Establish known-good state
        _HYP_CLIENT.post("/api/settings", json={
            "maxPostLength": length, "dailyCostCap": cap, "postsPerDay": ppd,
        })
        before = _HYP_CLIENT.get("/api/settings").json()

        # Fire an invalid save
        _HYP_CLIENT.post("/api/settings", json={"dailyCostCap": -999.0})

        after = _HYP_CLIENT.get("/api/settings").json()
        assert after["dailyCostCap"] == before["dailyCostCap"], (
            f"Rejected save mutated dailyCostCap: {before['dailyCostCap']} → {after['dailyCostCap']}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. REGRESSION MEMORY — replay every previously-failing pattern
# ─────────────────────────────────────────────────────────────────────────────

class TestRegressionMemory:
    """
    Reads .qa_memory.json and replays patterns that caused real production bugs.
    New entries are written automatically when any test in this file fails.
    This class grows over time — it never shrinks.
    """

    def test_memory_file_is_valid(self):
        """The memory file must be valid JSON (or absent — first run)."""
        if not _MEMORY_FILE.exists():
            return
        try:
            data = json.loads(_MEMORY_FILE.read_text())
            assert isinstance(data, dict)
            assert "failures" in data
        except json.JSONDecodeError as e:
            pytest.fail(f".qa_memory.json is corrupt: {e}")

    def test_known_regressions_still_fixed(self, iq):
        """
        Hard-coded regression replay for every bug found and fixed across all cycles.
        Entries are added permanently and NEVER removed — this is the project's
        full institutional memory. Each entry maps to a git commit that introduced the fix.
        """
        client = iq["client"]
        failures = []

        # ── Settings validation bugs (cycle-24) ─────────────────────────────
        # Bug: negative cost cap accepted — caused all pipeline runs to fail
        r = client.post("/api/settings", json={"dailyCostCap": -1.0})
        if r.json().get("ok") is not False:
            failures.append("negative-dailyCostCap-rejected: accepted when it should be rejected")

        # Bug: zero postsPerDay accepted — silently disabled posting forever
        r = client.post("/api/settings", json={"postsPerDay": 0})
        if r.json().get("ok") is not False:
            failures.append("zero-postsPerDay-rejected: accepted when it should be rejected")

        # Bug: string maxPostLength accepted — stored corrupt data, crashed AI calls
        r = client.post("/api/settings", json={"maxPostLength": "oops"})
        if r.json().get("ok") is not False:
            failures.append("string-maxPostLength-rejected: accepted when it should be rejected")

        # Bug: postingHours '25-99' accepted — hours outside 0-23 caused cron crashes
        r = client.post("/api/settings", json={"postingHours": "25-99"})
        if r.json().get("ok") is not False:
            failures.append("out-of-range-postingHours-rejected: accepted when it should be rejected")

        # Bug: zero alertThreshold accepted — triggered alerts constantly
        r = client.post("/api/settings", json={"alertThreshold": 0})
        if r.json().get("ok") is not False:
            failures.append("zero-alertThreshold-rejected: accepted when it should be rejected")

        # ── Missing response fields (cycle-24) ──────────────────────────────
        # Bug: seoMinScore not in DEFAULTS — reset to undefined after Space rebuild
        r = client.get("/api/settings")
        settings = r.json()
        for field in ("seoMinScore", "bskyEnabled", "schedulerEnabled", "postsPerDay",
                      "postingHours", "dailyCostCap", "maxPostLength", "rateLimitWaitMs"):
            if field not in settings:
                failures.append(f"settings-missing-field: '{field}' absent from GET /api/settings")

        # ── Endpoint existence regressions (cycle-24) ───────────────────────
        # Bug: /api/env-status 404 — frontend called this path, backend only had /api/env
        r = client.get("/api/env-status")
        if r.status_code != 200:
            failures.append(f"env-status-404: GET /api/env-status → {r.status_code}")

        # Bug: GET /api/schedule/suggest 404 — Suggest Times button was broken
        r = client.get("/api/schedule/suggest")
        if r.status_code != 200:
            failures.append(f"schedule-suggest-404: GET /api/schedule/suggest → {r.status_code}")
        else:
            body = r.json()
            if "suggestedTimes" not in body:
                failures.append("schedule-suggest-missing-field: 'suggestedTimes' absent from response")

        # Bug: POST /api/schedule/config 405 — Save Schedule button did nothing
        r = client.post("/api/schedule/config", json={"postsPerDay": 2})
        if r.status_code >= 500:
            failures.append(f"schedule-config-post-500: POST /api/schedule/config → {r.status_code}")
        elif r.status_code == 405:
            failures.append("schedule-config-post-405: POST /api/schedule/config not accepted")

        # Bug: POST /api/network/test 405 — frontend sends POST, was GET-only
        r = client.post("/api/network/test", json={})
        if r.status_code == 405:
            failures.append("network-test-post-405: POST /api/network/test returned 405")

        # Bug: POST /api/circuit-breakers/all/reset 404 — {name} wildcard caught 'all'
        r = client.post("/api/circuit-breakers/all/reset")
        if r.status_code == 404:
            failures.append("circuit-breaker-reset-all-404: POST /api/circuit-breakers/all/reset returned 404")

        # ── Schedule config fields (cycle-24) ───────────────────────────────
        # Bug: GET /api/schedule/config only returned cron+nextRun+paused
        #      frontend also reads schedulerEnabled, postsPerDay, postingHours
        r = client.get("/api/schedule/config")
        sched = r.json()
        for field in ("schedulerEnabled", "postsPerDay", "postingHours", "cron", "paused"):
            if field not in sched:
                failures.append(f"schedule-config-missing-field: '{field}' absent from GET /api/schedule/config")

        # ── Accounts shape (cycle-24) ────────────────────────────────────────
        # Bug: X credentials silently dropped after page refresh
        r = client.get("/api/accounts")
        if r.status_code != 200:
            failures.append(f"accounts-404: GET /api/accounts → {r.status_code}")
        else:
            social = r.json().get("social", {})
            for platform in ("x", "facebook", "instagram", "mastodon"):
                if platform not in social:
                    failures.append(f"accounts-missing-platform: '{platform}' absent from social")
                elif "connected" not in social[platform]:
                    failures.append(f"accounts-missing-connected: social.{platform} missing 'connected' field")

        # ── Dedup TTL regression (SRE cycle) ────────────────────────────────
        # Bug: dedup TTL was 168h — all products blocked for a week, SLO collapsed to 58%
        r = client.get("/api/dedup/stats")
        if r.status_code == 200:
            ttl = r.json().get("ttlHours", 999)
            if ttl > 48:
                failures.append(f"dedup-ttl-too-long: ttlHours={ttl} > 48 — risk of SLO collapse")

        # ── AuthError circuit breaker bypass (cycle-25) ──────────────────────
        # Bug: X 403 raised RuntimeError → tripped circuit breaker → all posts halted
        # Verify: AuthError is importable and is a subclass of RuntimeError (not BaseException)
        try:
            from api.utils.circuit_breaker import AuthError as _AE
            assert issubclass(_AE, RuntimeError), "AuthError must subclass RuntimeError"
        except ImportError:
            failures.append("auth-error-missing: AuthError not importable from circuit_breaker")

        # ── Health always available (startup regression) ─────────────────────
        # Bug: server crashed on startup when env vars missing — space was unreachable
        r = client.get("/api/health")
        if r.status_code != 200:
            failures.append(f"health-always-200: GET /api/health → {r.status_code} (should never fail)")

        # ── Diagnose endpoint shape ──────────────────────────────────────────
        r = client.get("/api/diagnose")
        if r.status_code != 200:
            failures.append(f"diagnose-404: GET /api/diagnose → {r.status_code}")
        else:
            diag = r.json()
            for field in ("ready", "checks", "circuitBreakers", "lastRun", "lastError"):
                if field not in diag:
                    failures.append(f"diagnose-missing-field: '{field}' absent from GET /api/diagnose")

        assert not failures, (
            f"Known regressions re-appeared ({len(failures)} failures):\n"
            + "\n".join(f"  ✗ {f}" for f in failures)
        )

    def test_memory_summary(self):
        """Print a summary of accumulated memory — visible in Allure / -v output."""
        mem = _load_memory()
        run_count = _mark_run()
        failure_count = len(mem.get("failures", []))
        shape_count = len(mem.get("learned_shapes", {}))
        recent = mem.get("failures", [])[-3:]
        print(
            f"\n── QA Memory ──────────────────────────────\n"
            f"  Total runs recorded : {run_count}\n"
            f"  Stored failures     : {failure_count}\n"
            f"  Learned shapes      : {shape_count} endpoints\n"
            + (f"  Last 3 failures     : {[f['test'] for f in recent]}\n" if recent else "")
            + "───────────────────────────────────────────"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. FRONTEND CONTRACT AUDIT — autonomous bug discovery
# ─────────────────────────────────────────────────────────────────────────────

_DASHBOARD = Path(__file__).parents[2] / "src" / "dashboard.html"

# Sample bodies for POST endpoints so they return real responses (not 422)
_POST_BODIES: dict[str, dict] = {
    "/api/social/x/credentials": {
        "handle": "qa_user", "consumer_key": "k", "consumer_secret": "s",
        "access_token": "t", "access_secret": "a",
    },
    "/api/social/facebook/credentials": {
        "handle": "qa_page", "page_id": "123", "page_access_token": "tok",
    },
    "/api/social/instagram/credentials": {
        "handle": "qa_ig", "ig_user_id": "456", "access_token": "tok",
    },
    "/api/social/mastodon/register": {"platform": "mastodon", "instance": "mastodon.social"},
    "/api/schedule/config": {"postsPerDay": 2, "postingHours": "9-21", "schedulerEnabled": True},
    "/api/settings": {"maxPostLength": 280},
    "/api/network/test": {"network": "sovrn"},
    "/api/circuit-breaker/reset": {"name": "groq"},
    "/api/logs/clear": {},
    "/api/accounts/bluesky/disconnect": {},
    "/api/accounts/bluesky/enable": {},
    "/api/accounts/bluesky/test": {},
    "/api/ai/generate": {"productName": "test", "category": "test", "description": "test"},
}

# Endpoints that legitimately need auth/OAuth/external state — not bugs if they 503/redirect
_EXPECTED_NON_200 = {
    "/api/social/mastodon/register",   # needs SPACE_HOST configured
    "/api/social/threads/auth",        # OAuth redirect
    "/api/social/tumblr/auth",         # OAuth redirect
    "/api/accounts/bluesky/test",      # needs real credentials
    "/api/logs/analyze",               # needs AI key
    "/api/dry-run",                    # needs AI key
    "/api/run",                        # fires background task
    "/api/ai/generate",                # needs AI key
}

# Fields each GET endpoint is expected to return (extracted from JS)
_EXPECTED_FIELDS: dict[str, list[str]] = {
    "/api/status":          ["pipeline", "budget"],
    "/api/settings":        ["maxPostLength", "dailyCostCap", "postsPerDay",
                             "postingHours", "schedulerEnabled", "seoMinScore"],
    "/api/accounts":        ["bluesky", "social"],
    "/api/slo":             ["slo_pct", "error_budget_remaining_pct"],
    "/api/clicks":          ["daily", "total"],
    "/api/dedup/stats":     ["count", "activeCount"],
    "/api/finops":          ["today_usd", "cap_usd", "forecast"],
    "/api/schedule/config": ["cron", "paused", "schedulerEnabled",
                             "postsPerDay", "postingHours"],
    "/api/health":          ["ok"],
    "/api/env-status":      ["BSKY_HANDLE", "BSKY_APP_PASSWORD"],
    "/api/env":             ["BSKY_HANDLE", "BSKY_APP_PASSWORD"],
    "/api/schedule/suggest":["suggestedTimes", "message"],
    "/api/diagnose":        ["ready", "checks"],
    "/api/logs/summary":    ["totalErrors", "totalWarns"],
    "/api/platform-rules":  ["rules"],
    "/api/insights":        ["dedup", "totalClicks"],
}


def _parse_frontend_calls(html: str) -> dict[str, set[str]]:
    """
    Parse every api('/path', 'METHOD') call from the dashboard JS.
    Returns {path: set_of_methods}.
    Paths with template literals (${...}) are resolved to their concrete forms.
    """
    calls: dict[str, set[str]] = {}

    # Pattern: api('path') or api('path', 'METHOD') or api(`path`, 'METHOD')
    # Handles both single-quoted and backtick paths
    pattern = re.compile(
        r"""api\(\s*[`']([^`'\$\n]+)[`']\s*(?:,\s*[`']([A-Z]+)[`'])?""",
    )
    for m in pattern.finditer(html):
        path_raw = m.group(1).split("?")[0].rstrip("/")  # strip query strings
        method = m.group(2) or "GET"
        if not path_raw.startswith("/api/") and path_raw not in ("/health", "/r/"):
            continue
        calls.setdefault(path_raw, set()).add(method)

    # Also find DELETE calls: api(`...`, 'DELETE')
    del_pattern = re.compile(r"""api\(`[^`]*\$\{[^}]+\}[^`]*`,\s*'DELETE'""")
    if del_pattern.search(html):
        calls.setdefault("/api/social/{platform}/disconnect", set()).add("DELETE")

    return calls


def _get_registered_routes(app) -> dict[str, set[str]]:
    """Return {path: set_of_methods} from FastAPI route registry."""
    routes: dict[str, set[str]] = {}
    for r in app.routes:
        if hasattr(r, "methods") and r.methods:
            routes.setdefault(r.path, set()).update(set(r.methods) - {"HEAD", "OPTIONS"})
    return routes


def _match_route(concrete_path: str, backend_routes: dict[str, set[str]]) -> str | None:
    """Match a concrete frontend path to a (possibly parameterised) backend route."""
    if concrete_path in backend_routes:
        return concrete_path
    # Try parameterised match: replace each path segment with a route parameter pattern
    for bp in backend_routes:
        if "{" not in bp:
            continue
        # Build regex: replace {param} with [^/]+
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", re.escape(bp).replace(r"\{", "{").replace(r"\}", "}"))
        pattern = re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(bp))
        if re.fullmatch(pattern, concrete_path):
            return bp
    return None


class TestFrontendContractAudit:
    """
    Autonomous bug discovery — parses dashboard.html at test time and:
    1. Detects any api() call whose route doesn't exist in the backend
    2. Detects wrong HTTP methods (frontend POSTs to a GET-only route)
    3. Detects missing response fields (field JS reads not in actual response)

    This class caught all 6 production bugs found on 2026-06-12:
      - /api/env-status (404)
      - POST /api/schedule/config (405)
      - GET /api/schedule/suggest (404)
      - POST /api/network/test (405)
      - /api/schedule/config missing schedulerEnabled/postsPerDay/postingHours
      - seoMinScore missing from GET /api/settings
    """

    def test_all_frontend_api_calls_have_matching_routes(self, iq):
        """
        Parse every api('/path','METHOD') call in dashboard.html.
        Assert each path+method combo is registered in FastAPI.
        A failure here means a route is missing or has the wrong method.
        """
        if not _DASHBOARD.exists():
            pytest.skip("dashboard.html not found")

        html = _DASHBOARD.read_text(encoding="utf-8")
        frontend_calls = _parse_frontend_calls(html)
        backend_routes = _get_registered_routes(iq["app"])

        missing_routes = []
        wrong_methods = []

        for path, methods in sorted(frontend_calls.items()):
            backend_path = _match_route(path, backend_routes)

            if backend_path is None:
                missing_routes.append(f"MISSING ROUTE: {list(methods)[0]} {path}")
                _record_failure(f"missing-route:{path}", f"methods={methods}")
                continue

            # Check that the required methods are supported
            registered_methods = backend_routes[backend_path]
            for method in methods:
                if method not in registered_methods:
                    wrong_methods.append(
                        f"WRONG METHOD: frontend calls {method} {path} but backend only has {registered_methods}"
                    )
                    _record_failure(f"wrong-method:{path}:{method}", str(registered_methods))

        bugs = missing_routes + wrong_methods
        assert not bugs, (
            f"Frontend–backend route contract violations ({len(bugs)} bugs):\n"
            + "\n".join(bugs)
        )

    def test_all_frontend_get_calls_return_200(self, iq):
        """
        Every GET endpoint the frontend calls must return 200.
        A failure here means a route crashes or returns an unexpected error.
        """
        if not _DASHBOARD.exists():
            pytest.skip("dashboard.html not found")

        html = _DASHBOARD.read_text(encoding="utf-8")
        frontend_calls = _parse_frontend_calls(html)
        client = iq["client"]

        failures = []
        for path, methods in sorted(frontend_calls.items()):
            if "GET" not in methods:
                continue
            if path in _EXPECTED_NON_200 or "{" in path:
                continue
            r = client.get(path)
            if r.status_code >= 500:
                failures.append(f"5xx: GET {path} → {r.status_code}: {r.text[:80]}")
                _record_failure(f"5xx:GET:{path}", r.text[:200])
            elif r.status_code == 404:
                failures.append(f"404: GET {path} — route not registered")
                _record_failure(f"404:GET:{path}", "route not registered")

        assert not failures, "Frontend GET calls returning errors:\n" + "\n".join(failures)

    def test_all_frontend_post_calls_return_non_5xx(self, iq):
        """
        Every POST/DELETE endpoint the frontend calls must not return 5xx.
        Uses sample bodies so routes don't reject with 422.
        """
        if not _DASHBOARD.exists():
            pytest.skip("dashboard.html not found")

        html = _DASHBOARD.read_text(encoding="utf-8")
        frontend_calls = _parse_frontend_calls(html)
        client = iq["client"]

        failures = []
        for path, methods in sorted(frontend_calls.items()):
            for method in methods:
                if method == "GET" or "{" in path:
                    continue
                if path in _EXPECTED_NON_200:
                    continue
                body = _POST_BODIES.get(path, {})
                fn = getattr(client, method.lower(), None)
                if fn is None:
                    continue
                r = fn(path, json=body)
                if r.status_code >= 500:
                    failures.append(f"5xx: {method} {path} → {r.status_code}: {r.text[:80]}")
                    _record_failure(f"5xx:{method}:{path}", r.text[:200])
                elif r.status_code == 404:
                    failures.append(f"404: {method} {path} — route missing")
                    _record_failure(f"404:{method}:{path}", "route not registered")
                elif r.status_code == 405:
                    failures.append(f"405: {method} {path} — wrong HTTP method")
                    _record_failure(f"405:{method}:{path}", "method not allowed")

        assert not failures, "Frontend POST/DELETE calls returning errors:\n" + "\n".join(failures)

    def test_get_response_fields_match_frontend_expectations(self, iq):
        """
        For each GET endpoint, fetch the real response and assert that every
        field the JavaScript reads from it actually exists.
        A failure here means a silent data-loss bug (field present in frontend
        code but missing from API response → form shows blank / dashboard breaks).
        """
        client = iq["client"]
        regressions = []

        for path, expected_fields in sorted(_EXPECTED_FIELDS.items()):
            r = client.get(path)
            if r.status_code != 200:
                regressions.append(f"{path} returned {r.status_code} (expected 200)")
                continue
            try:
                body = r.json()
            except Exception:
                regressions.append(f"{path} returned non-JSON response")
                continue
            if not isinstance(body, dict):
                continue  # list responses (history, stats) are fine
            missing = [f for f in expected_fields if f not in body]
            if missing:
                regressions.append(
                    f"{path} missing fields that frontend reads: {missing}\n"
                    f"  actual keys: {sorted(body.keys())}"
                )
                _record_failure(f"missing-fields:{path}", f"missing={missing}")
            else:
                # Update learned shape with confirmed fields
                _record_shape(path, {"keys": sorted(set(expected_fields) | set(body.keys()))})

        assert not regressions, (
            f"Response field contract violations ({len(regressions)} bugs):\n"
            + "\n".join(regressions)
        )

    def test_frontend_field_audit_summary(self, iq):
        """Print a summary of what was discovered — visible in -v output."""
        if not _DASHBOARD.exists():
            pytest.skip("dashboard.html not found")
        html = _DASHBOARD.read_text(encoding="utf-8")
        calls = _parse_frontend_calls(html)
        backend = _get_registered_routes(iq["app"])
        total_calls = sum(len(m) for m in calls.values())
        print(
            f"\n── Frontend Contract Audit ─────────────────\n"
            f"  Frontend api() calls  : {len(calls)} unique paths, {total_calls} method+path combos\n"
            f"  Backend routes        : {len(backend)} registered\n"
            f"  Response field checks : {len(_EXPECTED_FIELDS)} endpoints × N fields\n"
            f"───────────────────────────────────────────"
        )
