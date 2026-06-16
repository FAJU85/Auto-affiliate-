import importlib
import pytest


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.retry_budget as m
    importlib.reload(m)
    return m


def test_can_retry_unknown_resource(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.can_retry("svc") is True


def test_consume_allows_up_to_max(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.consume("svc", max_retries=3) is True
    assert m.consume("svc", max_retries=3) is True
    assert m.consume("svc", max_retries=3) is True


def test_consume_exhausted_after_max(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.consume("svc", max_retries=3)
    assert m.consume("svc", max_retries=3) is False


def test_can_retry_false_when_exhausted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.consume("svc", max_retries=3)
    assert m.can_retry("svc") is False


def test_remaining_full_for_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.remaining("svc", max_retries=3) == 3


def test_remaining_decrements(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.consume("svc", max_retries=3)
    assert m.remaining("svc") == 2


def test_remaining_zero_when_exhausted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.consume("svc", max_retries=3)
    assert m.remaining("svc") == 0


def test_reset_clears_count(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.consume("svc", max_retries=3)
    m.consume("svc", max_retries=3)
    m.reset("svc")
    assert m.remaining("svc") == 3


def test_reset_unknown_returns_false(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.reset("nonexistent") is False


def test_get_budget_none_for_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.get_budget("svc") is None


def test_get_budget_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.consume("svc", max_retries=3)
    b = m.get_budget("svc")
    for key in ("count", "max_retries", "exhausted", "last_retry"):
        assert key in b


def test_budget_summary_empty(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.budget_summary() == []


def test_budget_summary_structure(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.consume("svc", max_retries=3)
    s = m.budget_summary()
    assert len(s) == 1
    for key in ("resource", "count", "max_retries", "remaining", "exhausted"):
        assert key in s[0]


def test_budget_summary_sorted(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.consume("z_svc", max_retries=3)
    m.consume("a_svc", max_retries=3)
    resources = [x["resource"] for x in m.budget_summary()]
    assert resources == sorted(resources)


def test_multiple_resources_independent(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for _ in range(3):
        m.consume("svc_a", max_retries=3)
    assert m.can_retry("svc_b") is True
