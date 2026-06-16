import importlib


def _m(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import api.utils.latency_tracker as m
    importlib.reload(m)
    return m


def test_avg_latency_none_initially(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.avg_latency("groq") is None


def test_record_and_avg(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_latency("groq", 100.0)
    m.record_latency("groq", 200.0)
    assert m.avg_latency("groq") == 150.0


def test_p95_latency_none_initially(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.p95_latency("mistral") is None


def test_p95_latency_single_sample(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_latency("mistral", 300.0)
    assert m.p95_latency("mistral") == 300.0


def test_fastest_provider_returns_none_no_data(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    assert m.fastest_provider(["groq", "mistral"]) is None


def test_fastest_provider_picks_lowest_avg(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_latency("groq", 50.0)
    m.record_latency("mistral", 200.0)
    assert m.fastest_provider(["groq", "mistral"]) == "groq"


def test_fastest_provider_ignores_unknown(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_latency("groq", 50.0)
    assert m.fastest_provider(["groq", "unknown_provider"]) == "groq"


def test_latency_summary_keys(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    m.record_latency("groq", 100.0)
    summary = m.latency_summary()
    assert "groq" in summary
    assert "avg_ms" in summary["groq"]
    assert "p95_ms" in summary["groq"]
    assert "samples" in summary["groq"]


def test_max_samples_pruned(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    for i in range(60):
        m.record_latency("groq", float(i))
    summary = m.latency_summary()
    assert summary["groq"]["samples"] == 50


def test_track_context_manager(tmp_path, monkeypatch):
    m = _m(tmp_path, monkeypatch)
    with m.track("groq"):
        pass
    assert m.avg_latency("groq") is not None
