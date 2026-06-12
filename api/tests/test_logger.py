"""Unit tests for in-memory log ring buffer (utils/logger.py)."""

from api.utils import logger


def _reset():
    logger._RING.clear()


class TestEmit:
    def setup_method(self):
        _reset()

    def test_info_stored(self):
        logger.info("hello world", "test")
        logs = logger.get_recent_logs(1)
        assert len(logs) == 1
        assert logs[0]["msg"] == "hello world"
        assert logs[0]["level"] == "info"
        assert logs[0]["component"] == "test"

    def test_warn_stored(self):
        logger.warn("watch out", "pipeline")
        logs = logger.get_recent_logs(1)
        assert logs[-1]["level"] == "warn"

    def test_error_stored(self):
        logger.error("boom", "bluesky")
        logs = logger.get_recent_logs(1)
        assert logs[-1]["level"] == "error"
        assert logs[-1]["component"] == "bluesky"

    def test_default_component_is_system(self):
        logger.info("plain message")
        logs = logger.get_recent_logs(1)
        assert logs[-1]["component"] == "system"

    def test_get_recent_logs_limit(self):
        _reset()
        for i in range(10):
            logger.info(f"msg {i}")
        logs = logger.get_recent_logs(3)
        assert len(logs) == 3

    def test_get_recent_logs_all(self):
        _reset()
        for i in range(5):
            logger.info(f"entry {i}")
        logs = logger.get_recent_logs(100)
        assert len(logs) == 5


class TestClearLogs:
    def setup_method(self):
        _reset()

    def test_clear_returns_count(self):
        logger.info("a")
        logger.info("b")
        count = logger.clear_logs()
        assert count == 2
        assert logger.get_recent_logs(100) == []


class TestErrorSummary:
    def setup_method(self):
        _reset()

    def test_empty_summary(self):
        summary = logger.error_summary()
        assert summary["totalErrors"] == 0
        assert summary["totalWarns"] == 0
        assert summary["byComponent"] == {}
        assert summary["lastError"] is None

    def test_counts_errors(self):
        logger.error("err1", "pipeline")
        logger.error("err2", "pipeline")
        summary = logger.error_summary()
        assert summary["totalErrors"] == 2
        assert summary["byComponent"]["pipeline"]["errors"] == 2

    def test_counts_warns(self):
        logger.warn("w1", "bluesky")
        summary = logger.error_summary()
        assert summary["totalWarns"] == 1
        assert summary["byComponent"]["bluesky"]["warns"] == 1

    def test_last_error_is_most_recent(self):
        logger.error("first", "a")
        logger.error("second", "b")
        summary = logger.error_summary()
        assert summary["lastError"]["msg"] == "second"

    def test_info_not_counted(self):
        logger.info("no count")
        summary = logger.error_summary()
        assert summary["totalErrors"] == 0
        assert summary["totalWarns"] == 0
