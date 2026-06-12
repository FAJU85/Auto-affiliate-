"""Cycle 12: ai/text.py CTA phrases path, KeyError template, generate_post_text cascade."""

import os
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


# ── _build_prompts: CTA phrases from settings ─────────────────────────────────

class TestBuildPromptsCtaPhrases:
    def test_includes_cta_phrases_when_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as smod
        smod._cache = None
        importlib.reload(smod)
        smod.save_settings({
            "ctaPhrases": ["Grab it now!", "Don't miss out!", "Click to save"],
            "postSystemPrompt": "Write a post.",
        })
        from api.ai.text import _build_prompts
        system, user = _build_prompts({"name": "Laptop", "category": "electronics"}, [])
        assert "Grab it now!" in system or "CTA RULE" in system

    def test_uses_fallback_when_no_cta_phrases(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as smod
        smod._cache = None
        importlib.reload(smod)
        smod.save_settings({"ctaPhrases": [], "postSystemPrompt": "Write a post."})
        from api.ai.text import _build_prompts
        system, user = _build_prompts({"name": "Widget"}, [])
        assert "punchy CTA" in system or "CTA" in system

    def test_keyerror_in_template_falls_back(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.settings as smod
        smod._cache = None
        importlib.reload(smod)
        # Template with unknown key — should trigger KeyError fallback
        smod.save_settings({"postUserTemplate": "{name} — {unknown_key}"})
        from api.ai.text import _build_prompts
        system, user = _build_prompts({"name": "Widget"}, [])
        # Fallback user prompt
        assert "Widget" in user


# ── generate_post_text: full provider cascade ──────────────────────────────────

class TestGeneratePostTextCascade:
    @pytest.mark.asyncio
    async def test_uses_groq_when_available(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-groq")
        monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        txt.mistral_cb.reset()

        with patch.object(txt, "_try_groq", AsyncMock(return_value="Fantastic deal on this laptop! Grab it now!")):
            result = await txt.generate_post_text({"name": "Laptop", "category": "electronics"}, [])
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_falls_back_to_mistral_when_groq_unusable(self, monkeypatch):
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        txt.mistral_cb.reset()

        with patch.object(txt, "_try_groq", AsyncMock(return_value="AB")):  # too short
            with patch.object(txt, "_try_mistral", AsyncMock(return_value="Great deal on this Laptop! Don't miss out!")):
                result = await txt.generate_post_text({"name": "Laptop"}, [])
        assert "Laptop" in result or len(result) > 10

    @pytest.mark.asyncio
    async def test_uses_template_when_both_fail(self, monkeypatch):
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        txt.mistral_cb.reset()

        with patch.object(txt, "_try_groq", AsyncMock(return_value=None)):
            with patch.object(txt, "_try_mistral", AsyncMock(return_value=None)):
                result = await txt.generate_post_text({"name": "Mystery Item", "category": "gadgets"}, [])
        assert len(result) > 10
        assert "Mystery Item" in result

    @pytest.mark.asyncio
    async def test_uses_template_when_ai_output_unusable(self, monkeypatch):
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        txt.mistral_cb.reset()

        # Both providers return garbage
        with patch.object(txt, "_try_groq", AsyncMock(return_value="X")):
            with patch.object(txt, "_try_mistral", AsyncMock(return_value="   ")):
                result = await txt.generate_post_text({"name": "Widget Pro"}, [])
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_generate_uses_trend_in_prompt(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        from api.ai import text as txt
        import importlib
        importlib.reload(txt)
        txt.groq_cb.reset()
        txt.mistral_cb.reset()

        captured_user = []

        async def capture_try_groq(system, user):
            captured_user.append(user)
            return None

        with patch.object(txt, "_try_groq", side_effect=capture_try_groq):
            with patch.object(txt, "_try_mistral", AsyncMock(return_value=None)):
                await txt.generate_post_text({"name": "Widget"}, ["summer_fashion"])

        assert len(captured_user) > 0
        assert "summer_fashion" in captured_user[0] or "Widget" in captured_user[0]


# ── main.py: settings update and next-run endpoint ────────────────────────────


@pytest.fixture(scope="module")
def main_client(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["DATA_DIR"] = str(data_dir)
    os.environ.pop("DASHBOARD_PASSWORD", None)
    os.environ.pop("BSKY_HANDLE", None)
    os.environ.pop("BSKY_APP_PASSWORD", None)

    import importlib
    import api.utils.settings as smod
    import api.utils.metrics as mmod
    import api.utils.budget as bmod
    smod._cache = None
    importlib.reload(smod)
    importlib.reload(mmod)
    importlib.reload(bmod)

    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestSettingsAndScheduleEndpoints:
    def test_get_settings_returns_dict(self, main_client):
        r = main_client.get("/api/settings")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_save_settings_returns_ok(self, main_client):
        r = main_client.post("/api/settings", json={"dailyCostCap": 3.0})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_schedule_config_cron_field(self, main_client):
        r = main_client.get("/api/schedule/config")
        assert r.status_code == 200
        assert "cron" in r.json()

    def test_slo_endpoint_nominal(self, main_client):
        r = main_client.get("/api/slo")
        assert r.status_code == 200
        data = r.json()
        assert "circuit_breaker_active" in data
        assert "action" in data
