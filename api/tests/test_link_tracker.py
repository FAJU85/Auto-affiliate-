import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.link_tracker as m
    importlib.reload(m)
    return m


def test_register_returns_slug(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    slug = m.register_link("https://example.com/p1")
    assert isinstance(slug, str) and len(slug) == 8


def test_resolve_registered(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    slug = m.register_link("https://example.com/p1")
    assert m.resolve(slug) == "https://example.com/p1"


def test_resolve_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.resolve("notexist") is None


def test_same_url_returns_same_slug(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s1 = m.register_link("https://example.com/p1", platform="bluesky")
    s2 = m.register_link("https://example.com/p1", platform="bluesky")
    assert s1 == s2


def test_different_platform_different_slug(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s1 = m.register_link("https://example.com/p1", platform="bluesky")
    s2 = m.register_link("https://example.com/p1", platform="x")
    assert s1 != s2


def test_record_click_increments(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    slug = m.register_link("https://example.com/p1")
    m.record_click(slug)
    m.record_click(slug)
    assert m.get_stats(slug)["clicks"] == 2


def test_record_click_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.record_click("nope") is False


def test_get_stats_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    slug = m.register_link("https://example.com/p1", product_id="abc")
    stats = m.get_stats(slug)
    for key in ("url", "product_id", "clicks", "created_at", "last_clicked"):
        assert key in stats


def test_get_stats_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_stats("nope") is None


def test_top_links_ordered(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s1 = m.register_link("https://a.com")
    s2 = m.register_link("https://b.com")
    m.record_click(s2)
    m.record_click(s2)
    m.record_click(s1)
    top = m.top_links(2)
    assert top[0]["slug"] == s2


def test_top_links_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.top_links() == []


def test_link_summary_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    s = m.link_summary()
    assert s["total_links"] == 0
    assert s["total_clicks"] == 0
    assert s["top_slug"] is None


def test_link_summary_counts(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    slug = m.register_link("https://a.com")
    m.record_click(slug)
    m.record_click(slug)
    s = m.link_summary()
    assert s["total_links"] == 1
    assert s["total_clicks"] == 2
    assert s["top_slug"] == slug
