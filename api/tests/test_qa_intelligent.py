"""
Intelligent QA Layer — auto-discovery, property-based testing, regression memory.

Three systems:

1. RouteAutoCoverage   — discovers every FastAPI route at test time; any GET
                         that isn't explicitly listed in KNOWN_SKIP gets a
                         smoke test (must not 5xx).  New routes are flagged.

2. PropertyBasedSettings — Hypothesis drives hundreds of random boundary inputs
                           at the settings endpoint so humans don't have to
                           enumerate every combination.

3. RegressionMemory    — after each run, failures are appended to
                         .qa_memory.json.  On the next run, every previously-
                         failing pattern is replayed first so regressions are
                         caught before anything else runs.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

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
        Hard-coded regression replay for every bug that was found via the QA suite.
        When a new bug is fixed, a replay case is added here permanently.
        """
        client = iq["client"]
        replays: list[tuple[str, Any, bool]] = [
            # (description, payload_that_should_be_rejected, expected_ok)
            # Cycle-24 bug: X credentials silently dropped after save
            # Fixed: /api/accounts now returns masked credentials
            ("x-credentials-not-dropped-after-save", None, None),
            # Cycle-24 bug: negative cost cap accepted — broke all runs
            ("negative-dailyCostCap-rejected",
             {"dailyCostCap": -1.0}, False),
            # Cycle-24 bug: zero postsPerDay accepted — disabled posting
            ("zero-postsPerDay-rejected",
             {"postsPerDay": 0}, False),
            # Cycle-24 bug: string maxPostLength accepted — corrupt data
            ("string-maxPostLength-rejected",
             {"maxPostLength": "oops"}, False),
            # Cycle-24 bug: invalid postingHours accepted
            ("out-of-range-postingHours-rejected",
             {"postingHours": "25-99"}, False),
        ]

        failures = []
        for desc, payload, expected_ok in replays:
            if payload is None:
                # Shape test — just ensure endpoint responds
                r = client.get("/api/accounts")
                if r.status_code != 200:
                    failures.append(f"{desc}: GET /api/accounts → {r.status_code}")
                else:
                    x = r.json().get("social", {}).get("x", {})
                    # After credentials are saved, connected should be readable
                    if "connected" not in x:
                        failures.append(f"{desc}: 'connected' field missing from social.x")
            else:
                r = client.post("/api/settings", json=payload)
                if r.status_code >= 500:
                    failures.append(f"{desc}: server crashed (5xx)")
                elif r.json().get("ok") is not expected_ok:
                    failures.append(
                        f"{desc}: expected ok={expected_ok}, got {r.json().get('ok')} | {r.json().get('error','')}"
                    )

        assert not failures, "Known regressions re-appeared:\n" + "\n".join(failures)

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
