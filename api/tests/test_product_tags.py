import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.product_tags as m
    importlib.reload(m)
    return m


def test_get_tags_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_tags("Sony Headphones") == []


def test_add_tag_persists(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Sony Headphones", "bestseller")
    assert "bestseller" in m.get_tags("Sony Headphones")


def test_add_tag_no_duplicates(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Product A", "featured")
    m.add_tag("Product A", "featured")
    assert m.get_tags("Product A").count("featured") == 1


def test_add_tag_case_insensitive(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Product B", "CLEARANCE")
    assert "clearance" in m.get_tags("Product B")


def test_remove_tag_returns_true(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Product C", "sale")
    assert m.remove_tag("Product C", "sale") is True


def test_remove_tag_removes_it(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Product D", "new")
    m.remove_tag("Product D", "new")
    assert "new" not in m.get_tags("Product D")


def test_remove_tag_returns_false_when_absent(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.remove_tag("Product E", "notexist") is False


def test_has_tag_true(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Product F", "hot")
    assert m.has_tag("Product F", "hot") is True


def test_has_tag_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.has_tag("Product G", "hot") is False


def test_get_all_tags_returns_dict(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("P1", "tag1")
    result = m.get_all_tags()
    assert isinstance(result, dict)


def test_products_with_tag(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Alpha", "deal")
    m.add_tag("Beta", "deal")
    m.add_tag("Gamma", "other")
    found = m.products_with_tag("deal")
    assert "alpha" in found
    assert "beta" in found
    assert "gamma" not in found


def test_add_multiple_tags(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.add_tag("Multi", "a")
    m.add_tag("Multi", "b")
    assert len(m.get_tags("Multi")) == 2
