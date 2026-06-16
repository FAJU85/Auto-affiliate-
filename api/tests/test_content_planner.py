import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.content_planner as m
    importlib.reload(m)
    return m


def test_add_item_returns_id(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Summer sale post", theme="deals", platforms=["twitter"])
    assert isinstance(item_id, str) and len(item_id) > 0


def test_get_item_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    item = m.get_item(item_id)
    for key in ("id", "title", "theme", "platforms", "status", "created_at", "published_at"):
        assert key in item


def test_initial_status_draft(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    assert m.get_item(item_id)["status"] == "draft"


def test_get_item_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_item("nonexistent") is None


def test_update_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    assert m.update_status(item_id, "scheduled") is True
    assert m.get_item(item_id)["status"] == "scheduled"


def test_update_status_published_sets_timestamp(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    m.update_status(item_id, "published")
    assert m.get_item(item_id)["published_at"] is not None


def test_update_status_invalid(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    with pytest.raises(ValueError):
        m.update_status(item_id, "invalid")


def test_update_status_unknown_item(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.update_status("nonexistent", "scheduled") is False


def test_get_by_status(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    items = m.get_by_status("draft")
    assert any(i["id"] == item_id for i in items)


def test_get_by_status_excludes_other(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    m.update_status(item_id, "published")
    assert m.get_by_status("draft") == []


def test_get_by_theme(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_item("A", theme="deals", platforms=["twitter"])
    m.add_item("B", theme="travel", platforms=["instagram"])
    items = m.get_by_theme("deals")
    assert len(items) == 1
    assert items[0]["theme"] == "deals"


def test_get_by_platform(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_item("A", theme="deals", platforms=["twitter", "bluesky"])
    m.add_item("B", theme="deals", platforms=["instagram"])
    items = m.get_by_platform("twitter")
    assert len(items) == 1


def test_delete_item(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    item_id = m.add_item("Post", theme="deals", platforms=["twitter"])
    assert m.delete_item(item_id) is True
    assert m.get_item(item_id) is None


def test_delete_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.delete_item("nonexistent") is False


def test_planner_stats(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_item("A", theme="deals", platforms=["twitter"])
    m.add_item("B", theme="travel", platforms=["instagram"])
    s = m.planner_stats()
    assert s["total"] == 2
    assert s["draft"] == 2
    assert "deals" in s["themes"]
