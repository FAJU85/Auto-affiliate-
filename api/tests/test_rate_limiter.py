import importlib


def _get():
    import api.utils.rate_limiter as m
    importlib.reload(m)
    return m


def test_first_request_allowed():
    m = _get()
    assert m.is_allowed("/api/run", limit=5) is True


def test_within_limit_allowed():
    m = _get()
    for _ in range(4):
        m.is_allowed("/test", limit=5)
    assert m.is_allowed("/test", limit=5) is True


def test_at_limit_blocked():
    m = _get()
    for _ in range(5):
        m.is_allowed("/test2", limit=5)
    assert m.is_allowed("/test2", limit=5) is False


def test_reset_clears_endpoint():
    m = _get()
    for _ in range(5):
        m.is_allowed("/test3", limit=5)
    m.reset("/test3")
    assert m.is_allowed("/test3", limit=5) is True


def test_reset_all_clears_buckets():
    m = _get()
    for _ in range(5):
        m.is_allowed("/a", limit=5)
    m.reset()
    assert m.request_count("/a") == 0


def test_request_count_increments():
    m = _get()
    m.is_allowed("/cnt", limit=10)
    m.is_allowed("/cnt", limit=10)
    assert m.request_count("/cnt") == 2


def test_default_limit_used_when_not_specified():
    m = _get()
    assert m.is_allowed("/api/run") is True


def test_rate_limit_status_returns_dict():
    m = _get()
    m.is_allowed("/api/run", limit=10)
    status = m.rate_limit_status()
    assert isinstance(status, dict)


def test_rate_limit_status_contains_endpoint():
    m = _get()
    m.is_allowed("/api/preview", limit=10)
    status = m.rate_limit_status()
    assert "/api/preview" in status


def test_rate_limit_status_has_required_keys():
    m = _get()
    m.is_allowed("/api/run", limit=10)
    status = m.rate_limit_status()
    ep = next(iter(status.values()))
    assert "count_last_60s" in ep
    assert "limit" in ep


def test_different_endpoints_independent():
    m = _get()
    for _ in range(3):
        m.is_allowed("/ep_a", limit=3)
    assert m.is_allowed("/ep_a", limit=3) is False
    assert m.is_allowed("/ep_b", limit=3) is True
