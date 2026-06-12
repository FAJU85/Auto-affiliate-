"""Unit + integration tests for settings persistence (PF-09)."""

import json
import pytest


@pytest.fixture()
def settings_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import importlib
    import api.utils.settings as smod
    smod._cache = None  # clear in-memory cache
    importlib.reload(smod)
    yield smod
    smod._cache = None
    importlib.reload(smod)


class TestGetSettings:
    def test_returns_defaults_when_no_file(self, settings_mod):
        s = settings_mod.get_settings()
        assert s["dailyCostCap"] == 2.00
        assert s["schedulerEnabled"] is True
        assert "bluesky" in s["publishPlatforms"]

    def test_merges_file_over_defaults(self, settings_mod, tmp_path):
        (tmp_path / "settings.json").write_text(json.dumps({"dailyCostCap": 5.0}))
        settings_mod._cache = None
        s = settings_mod.get_settings()
        assert s["dailyCostCap"] == 5.0
        assert s["schedulerEnabled"] is True  # default still present

    def test_cache_returns_same_object(self, settings_mod):
        s1 = settings_mod.get_settings()
        s2 = settings_mod.get_settings()
        assert s1 is s2

    def test_stale_system_prompt_reset_to_default(self, settings_mod, tmp_path):
        old_prompt = (
            "You are a Bluesky social media copywriter. Write ONE short affiliate post "
            "in ENGLISH ONLY. Rules: max 200 characters, no markdown (no **, no ##), "
            "no emojis unless essential, no hashtags, no URLs, no ALL CAPS words, "
            "conversational tone, one clear call-to-action. Reply with only the post text "
            "— nothing else."
        )
        (tmp_path / "settings.json").write_text(json.dumps({"postSystemPrompt": old_prompt}))
        settings_mod._cache = None
        s = settings_mod.get_settings()
        # Stale prompt must be replaced with the current default
        assert s["postSystemPrompt"] != old_prompt
        assert "benefit" in s["postSystemPrompt"].lower()

    def test_empty_prompt_reset_to_default(self, settings_mod, tmp_path):
        (tmp_path / "settings.json").write_text(json.dumps({"postSystemPrompt": ""}))
        settings_mod._cache = None
        s = settings_mod.get_settings()
        assert len(s["postSystemPrompt"]) > 20


class TestSaveSettings:
    def test_persists_to_disk(self, settings_mod, tmp_path):
        settings_mod.save_settings({"dailyCostCap": 3.0})
        raw = json.loads((tmp_path / "settings.json").read_text())
        assert raw["dailyCostCap"] == 3.0

    def test_atomic_write_no_tmp_file(self, settings_mod, tmp_path):
        settings_mod.save_settings({"dailyCostCap": 3.0})
        assert not list(tmp_path.glob("*.tmp"))

    def test_partial_update_preserves_other_keys(self, settings_mod):
        settings_mod.save_settings({"dailyCostCap": 9.99})
        s = settings_mod.get_settings()
        assert s["schedulerEnabled"] is True  # untouched default
        assert s["dailyCostCap"] == 9.99


class TestGetSpaceHost:
    def test_returns_empty_when_no_env(self, settings_mod, monkeypatch):
        monkeypatch.delenv("SPACE_HOST", raising=False)
        monkeypatch.delenv("SPACE_ID", raising=False)
        assert settings_mod.get_space_host() == ""

    def test_constructs_from_space_id(self, settings_mod, monkeypatch):
        monkeypatch.delenv("SPACE_HOST", raising=False)
        monkeypatch.setenv("SPACE_ID", "vooom/fast-growth")
        host = settings_mod.get_space_host()
        assert host == "https://vooom-fast-growth.hf.space"

    def test_adds_https_if_missing(self, settings_mod, monkeypatch):
        monkeypatch.setenv("SPACE_HOST", "vooom-fast-growth.hf.space")
        host = settings_mod.get_space_host()
        assert host.startswith("https://")
