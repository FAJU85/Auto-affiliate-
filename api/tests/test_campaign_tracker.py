import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.campaign_tracker as m
    importlib.reload(m)
    return m


def test_list_campaigns_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.list_campaigns() == []


def test_create_campaign_returns_dict(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.create_campaign("Summer Sale")
    assert isinstance(result, dict)


def test_create_campaign_has_required_keys(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    result = m.create_campaign("Test")
    for key in ("id", "name", "description", "created_at", "posts"):
        assert key in result


def test_list_campaigns_after_create(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.create_campaign("Campaign A")
    m.create_campaign("Campaign B")
    assert len(m.list_campaigns()) == 2


def test_get_campaign_returns_correct(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    c = m.create_campaign("My Campaign")
    result = m.get_campaign(c["id"])
    assert result["name"] == "My Campaign"


def test_get_campaign_unknown_returns_none(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_campaign("notexist") is None


def test_add_post_to_campaign(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    c = m.create_campaign("Sale")
    run = {"success": True, "clicks": 5, "platform": "bluesky"}
    assert m.add_post_to_campaign(c["id"], run) is True
    assert len(m.get_campaign(c["id"])["posts"]) == 1


def test_add_post_unknown_campaign(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.add_post_to_campaign("badid", {}) is False


def test_campaign_stats_keys(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    c = m.create_campaign("Stats Test")
    stats = m.campaign_stats(c["id"])
    for key in ("id", "name", "total_posts", "successful_posts", "total_clicks", "avg_clicks"):
        assert key in stats


def test_campaign_stats_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    c = m.create_campaign("Count Test")
    m.add_post_to_campaign(c["id"], {"success": True, "clicks": 10, "platform": "x"})
    m.add_post_to_campaign(c["id"], {"success": False, "clicks": 0, "platform": "x"})
    stats = m.campaign_stats(c["id"])
    assert stats["total_posts"] == 2
    assert stats["successful_posts"] == 1
    assert stats["total_clicks"] == 10


def test_delete_campaign(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    c = m.create_campaign("To Delete")
    assert m.delete_campaign(c["id"]) is True
    assert m.get_campaign(c["id"]) is None


def test_delete_unknown_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.delete_campaign("nosuchid") is False
