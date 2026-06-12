"""Cycle 22: direct module tests without reload to hit exception handler branches."""

import time
import os


# ── bluesky_client.py: file-op exception handlers (direct, no reload) ─────────

class TestBlueskyFileExceptionsDirect:
    def test_save_ratelimit_exception_swallowed(self, tmp_path):
        """Lines 47-48: exception in _save_ratelimit is swallowed."""
        from api.bluesky_client import _save_ratelimit

        # Write to a path under a read-only dir
        readonly_dir = tmp_path / "ro"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)

        from unittest.mock import patch
        ro_path = readonly_dir / "sub"

        # Patch DATA_DIR to point to read-only location
        with patch("api.bluesky_client.DATA_DIR", ro_path):
            with patch("api.bluesky_client.RATELIMIT_FILE", ro_path / "ratelimit.json"):
                # Should not raise despite mkdir failing
                _save_ratelimit(time.time() + 3600)

        os.chmod(str(readonly_dir), 0o755)

    def test_clear_ratelimit_permission_error_swallowed(self, tmp_path):
        """Lines 53-54: PermissionError in unlink is swallowed."""
        from api.bluesky_client import _clear_ratelimit

        # Create a file that we'll make read-only
        ratelimit_file = tmp_path / "ratelimit.json"
        ratelimit_file.write_text('{"reset": 9999}')
        parent = tmp_path
        os.chmod(str(parent), 0o555)  # read+execute only — can't delete files

        from unittest.mock import patch
        with patch("api.bluesky_client.RATELIMIT_FILE", ratelimit_file):
            # Unlink should fail due to permissions → exception swallowed
            _clear_ratelimit()

        os.chmod(str(parent), 0o755)

    def test_clear_session_permission_error_swallowed(self, tmp_path):
        """Lines 102-103: PermissionError in unlink is swallowed."""
        from api.bluesky_client import _clear_session

        session_file = tmp_path / "session.json"
        session_file.write_text('{"accessJwt": "jwt"}')
        parent = tmp_path
        os.chmod(str(parent), 0o555)

        from unittest.mock import patch
        with patch("api.bluesky_client.SESSION_FILE", session_file):
            _clear_session()

        os.chmod(str(parent), 0o755)


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
            # Non-API path without auth header → line 119 (call_next is called)
            r = client.get("/")
        assert r.status_code == 200

        os.environ.pop("DASHBOARD_PASSWORD", None)
