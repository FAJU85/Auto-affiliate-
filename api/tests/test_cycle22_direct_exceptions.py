"""Cycle 22: direct module tests without reload to hit exception handler branches."""

import time
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── bluesky_client.py: file-op exception handlers (direct, no reload) ─────────

class TestBlueskyFileExceptionsDirect:
    def test_save_ratelimit_exception_swallowed(self, tmp_path):
        """Lines 47-48: exception in _save_ratelimit is swallowed."""
        from api.bluesky_client import _save_ratelimit

        bad_path = MagicMock(spec=Path)
        bad_path.mkdir.side_effect = PermissionError("no write")
        bad_ratelimit = MagicMock(spec=Path)
        bad_ratelimit.write_text.side_effect = PermissionError("no write")

        with patch("api.bluesky_client.DATA_DIR", bad_path):
            with patch("api.bluesky_client.RATELIMIT_FILE", bad_ratelimit):
                _save_ratelimit(time.time() + 3600)

    def test_clear_ratelimit_permission_error_swallowed(self, tmp_path):
        """Lines 53-54: PermissionError in unlink is swallowed."""
        from api.bluesky_client import _clear_ratelimit

        bad_ratelimit = MagicMock(spec=Path)
        bad_ratelimit.unlink.side_effect = PermissionError("no delete")

        with patch("api.bluesky_client.RATELIMIT_FILE", bad_ratelimit):
            _clear_ratelimit()

    def test_clear_session_permission_error_swallowed(self, tmp_path):
        """Lines 102-103: PermissionError in unlink is swallowed."""
        from api.bluesky_client import _clear_session

        bad_session = MagicMock(spec=Path)
        bad_session.unlink.side_effect = PermissionError("no delete")

        with patch("api.bluesky_client.SESSION_FILE", bad_session):
            _clear_session()


# ── main.py: line 119 (auth middleware passthrough for non-API paths) ──────────

class TestMainAuthMiddlewareDirect:
    def test_unauthenticated_non_api_path_returns_html(self, tmp_path, monkeypatch):
        """Line 119: unauthenticated request to non-API path passes through."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        os.environ["DASHBOARD_PASSWORD"] = "secret"  # pragma: allowlist secret

        import importlib
        import api.utils.settings as smod
        import api.utils.metrics as mmod
        import api.utils.budget as bmod
        smod._cache = None
        importlib.reload(smod)
        importlib.reload(mmod)
        importlib.reload(bmod)

        from fastapi.testclient import TestClient
        from api.main import app
        with TestClient(app, raise_server_exceptions=False) as client:
            # Non-API, non-public-exact path without auth → line 119
            r = client.get("/dashboard")
        assert r.status_code in (200, 404)

        os.environ.pop("DASHBOARD_PASSWORD", None)
