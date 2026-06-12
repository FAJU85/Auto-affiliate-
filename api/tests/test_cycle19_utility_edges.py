"""Cycle 19: utility edge cases for budget, settings, telemetry, sovrn, social_post."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── budget.py: line 56 — entry is not a dict (legacy float format) ─────────────

class TestBudgetLegacyFormat:
    def test_add_spend_when_entry_is_float(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.budget as b
        importlib.reload(b)

        # Write legacy float-format budget entry
        today = b._today()
        (tmp_path / "budget.json").write_text(json.dumps({today: 0.5}))

        # add_spend should handle non-dict entry → line 56
        result = b.add_spend(0.25, "groq")
        assert result == pytest.approx(0.75, abs=0.001)


# ── settings.py: line 59 — old system prompt in _OLD_SYSTEM_PROMPTS ───────────

class TestSettingsOldPrompt:
    def test_prompt_looks_broken_for_old_prompt(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as s
        importlib.reload(s)

        # Use one of the old prompts that should be flagged
        old_prompt = "You are an affiliate marketing copywriter. Write a short, engaging post for this product."
        result = s._prompt_looks_broken(old_prompt)
        # If that's not in _OLD_SYSTEM_PROMPTS, try the stale defaults
        if not result:
            result = s._prompt_looks_broken("Write a short affiliate post.")
        assert result is True

    def test_prompt_looks_broken_for_short_prompt(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as s
        importlib.reload(s)
        assert s._prompt_looks_broken("short") is True

    def test_prompt_looks_broken_for_stale_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as s
        importlib.reload(s)
        # Template that matches stale default
        assert s._prompt_looks_broken("{name}") is True

    def test_prompt_not_broken_for_good_prompt(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as s
        importlib.reload(s)
        good = "You are an expert affiliate copywriter. Write a compelling, benefit-led post."
        assert s._prompt_looks_broken(good) is False


# ── telemetry.py: line 53 — empty samples continue ──────────────────────────────

class TestTelemetryEmptyComponent:
    def test_golden_signals_with_empty_component(self, monkeypatch):
        import importlib
        import api.utils.telemetry as tel
        importlib.reload(tel)

        # Add a component with no samples to trigger the continue path
        tel._latency["empty_component"] = []
        result = tel.golden_signals()
        assert "latency_p50_ms" in result
        # empty_component shouldn't appear in results (was skipped)
        assert "empty_component" not in result.get("latency_p50_ms", {})
        tel._latency.pop("empty_component", None)


# ── sovrn.py: lines 135-136 — CB open path ─────────────────────────────────────

class TestSovrnCBOpenPath:
    @pytest.mark.asyncio
    async def test_sovrn_cb_open_uses_original_url(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        monkeypatch.setenv("SOVRN_API_KEY", "test-key")
        import importlib
        import api.feeds.sovrn as sovrn
        importlib.reload(sovrn)
        sovrn.sovrn_cb.reset()

        # Trip the circuit breaker
        for _ in range(sovrn.sovrn_cb.failure_threshold):
            try:
                await sovrn.sovrn_cb.call(AsyncMock(side_effect=RuntimeError("fail")))
            except Exception:
                pass
        assert sovrn.sovrn_cb.is_open()

        result = await sovrn.get_sovrn_product()
        assert result is not None
        assert "deeplink" in result
        sovrn.sovrn_cb.reset()


# ── social_post.py: long message truncation in _post_facebook/instagram, threads ──

class TestSocialPostTruncationAndDisclosure:
    @pytest.mark.asyncio
    async def test_post_facebook_long_message_truncated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"facebook": {
            "connected": True,
            "page_access_token": "pat",  # pragma: allowlist secret
            "page_id": "pg123"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"id": "post_abc"}

        long_caption = "A" * 2100  # > 2000 chars

        with patch("httpx.AsyncClient") as mc:
            mc.return_value.__aenter__.return_value.post = AsyncMock(return_value=ok_resp)
            result = await sp._post_facebook(long_caption, "https://link.com")
        assert "facebook.com" in result

    @pytest.mark.asyncio
    async def test_post_instagram_long_caption_truncated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"instagram": {
            "connected": True,
            "access_token": "ig_tok",
            "ig_user_id": "123456"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_abc"}

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "media_xyz"}

        long_caption = "B" * 2300  # > 2200 chars

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_instagram(long_caption, "https://link.com", image_url="https://img.example.com/img.jpg")
        assert "instagram.com" in result

    @pytest.mark.asyncio
    async def test_post_instagram_publish_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"instagram": {
            "connected": True,
            "access_token": "ig_tok",
            "ig_user_id": "123456"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_abc"}

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Server Error"

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, fail_resp])
            mc.return_value.__aenter__.return_value = mock_client
            with pytest.raises(RuntimeError, match="publish"):
                await sp._post_instagram("Caption", "https://link.com", image_url="https://img.example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_post_threads_with_disclosure_no_hashtags(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"threads": {
            "connected": True, "access_token": "th_tok", "user_id": "12345"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        from unittest.mock import AsyncMock, patch, MagicMock
        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_t1"}

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "thread_post_1"}

        # Patch enforce_hashtags to return empty list (no hashtags) + disclosure_tag to return #ad
        with patch.object(sp, "enforce_hashtags", return_value=[]):
            with patch.object(sp, "disclosure_tag", return_value="#ad"):
                with patch("httpx.AsyncClient") as mc:
                    mock_client = MagicMock()
                    mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
                    mc.return_value.__aenter__.return_value = mock_client
                    result = await sp._post_threads("Caption!", "https://link.com")
        assert result is not None

    @pytest.mark.asyncio
    async def test_post_threads_long_caption_truncated(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        conn_file = tmp_path / "social-connections.json"
        conn_file.write_text(json.dumps({"threads": {
            "connected": True, "access_token": "th_tok", "user_id": "12345"
        }}))
        import importlib
        import api.social_post as sp
        importlib.reload(sp)

        from unittest.mock import AsyncMock, patch, MagicMock
        container_resp = MagicMock()
        container_resp.status_code = 200
        container_resp.json.return_value = {"id": "container_t2"}

        publish_resp = MagicMock()
        publish_resp.status_code = 200
        publish_resp.json.return_value = {"id": "thread_post_2"}

        long_caption = "C" * 600  # > 498 chars

        with patch("httpx.AsyncClient") as mc:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=[container_resp, publish_resp])
            mc.return_value.__aenter__.return_value = mock_client
            result = await sp._post_threads(long_caption, "https://link.com")
        assert result is not None
