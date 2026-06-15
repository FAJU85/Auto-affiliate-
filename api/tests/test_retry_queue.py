"""Tests for the retry queue (Build #5)."""

import time
import pytest
from unittest.mock import AsyncMock, patch


_PRODUCT = {
    "name": "Test Widget",
    "price": 99.0,
    "deeplink": "https://example.com/dp/B001",
    "source": "sovrn",
}


# ── retry_queue unit ───────────────────────────────────────────────────────────

class TestRetryQueueEnqueue:
    def test_enqueue_adds_entry(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("instagram", "Great product!", "https://r.example.com/x", _PRODUCT)
        assert rq.queue_depth() == 1

    def test_enqueue_sets_attempts_to_1(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("mastodon", "Caption", "https://r.example.com/y", _PRODUCT)
        entries = rq._load()
        assert entries[0]["attempts"] == 1

    def test_enqueue_sets_next_retry_in_future(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        before = time.time()
        rq.enqueue("x", "Caption", "https://r.example.com/z", _PRODUCT)
        entries = rq._load()
        assert entries[0]["next_retry_at"] > before

    def test_multiple_enqueues_accumulate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("bluesky", "Caption 1", "https://r.example.com/1", _PRODUCT)
        rq.enqueue("instagram", "Caption 2", "https://r.example.com/2", _PRODUCT)
        assert rq.queue_depth() == 2


class TestRetryQueueGetDue:
    def test_not_due_yet_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("instagram", "Caption", "https://r.example.com/nd", _PRODUCT)
        # next_retry_at is 15 min in the future — not due yet
        assert rq.get_due() == []

    def test_past_next_retry_is_due(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("instagram", "Caption", "https://r.example.com/due", _PRODUCT)
        # Force next_retry_at to the past
        entries = rq._load()
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)

        assert len(rq.get_due()) == 1

    def test_max_attempts_not_returned(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("facebook", "Caption", "https://r.example.com/max", _PRODUCT)
        entries = rq._load()
        entries[0]["attempts"] = rq.MAX_ATTEMPTS
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)

        assert rq.get_due() == []

    def test_expired_entry_not_returned(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("threads", "Caption", "https://r.example.com/exp", _PRODUCT)
        entries = rq._load()
        entries[0]["next_retry_at"] = time.time() - 1
        entries[0]["created_at"] = time.time() - rq.EXPIRY_S - 1
        rq._save(entries)

        assert rq.get_due() == []


class TestRetryQueueMarkSuccess:
    def test_removes_entry(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("bluesky", "Cap", "https://r.example.com/s1", _PRODUCT)
        entries = rq._load()
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)
        due = rq.get_due()
        rq.mark_success(due[0])
        assert rq.queue_depth() == 0


class TestRetryQueueMarkFailed:
    def test_increments_attempts(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("mastodon", "Cap", "https://r.example.com/f1", _PRODUCT)
        entries = rq._load()
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)
        due = rq.get_due()
        rq.mark_failed(due[0], error="timeout")
        remaining = rq._load()
        assert remaining[0]["attempts"] == 2

    def test_drops_at_max_attempts(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("x", "Cap", "https://r.example.com/f2", _PRODUCT)
        entries = rq._load()
        entries[0]["attempts"] = rq.MAX_ATTEMPTS - 1
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)
        due = rq.get_due()
        rq.mark_failed(due[0], error="final fail")
        assert rq.queue_depth() == 0


class TestClearExpired:
    def test_removes_expired_entries(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("instagram", "Cap", "https://r.example.com/ce", _PRODUCT)
        entries = rq._load()
        entries[0]["created_at"] = time.time() - rq.EXPIRY_S - 1
        rq._save(entries)
        removed = rq.clear_expired()
        assert removed == 1
        assert rq.queue_depth() == 0

    def test_keeps_fresh_entries(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("instagram", "Cap", "https://r.example.com/kf", _PRODUCT)
        removed = rq.clear_expired()
        assert removed == 0
        assert rq.queue_depth() == 1


# ── retry_failed_posts integration ────────────────────────────────────────────

class TestRetryFailedPosts:
    @pytest.mark.asyncio
    async def test_returns_zero_when_queue_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        from api import pipeline
        monkeypatch.setattr(pipeline, "retry_queue", rq)
        result = await pipeline.retry_failed_posts()
        assert result["retried"] == 0

    @pytest.mark.asyncio
    async def test_retries_due_entry_and_marks_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("instagram", "Great product!", "https://r.example.com/ri", _PRODUCT)
        entries = rq._load()
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)

        from api import pipeline
        monkeypatch.setattr(pipeline, "retry_queue", rq)

        with patch("api.pipeline.post_to_platform", AsyncMock(return_value="https://ig.post/1")):
            result = await pipeline.retry_failed_posts()

        assert result["succeeded"] == 1
        assert rq.queue_depth() == 0

    @pytest.mark.asyncio
    async def test_marks_failed_when_no_uri(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path))
        import importlib
        import api.utils.retry_queue as rq
        rq.DATA_DIR = tmp_path
        importlib.reload(rq)

        rq.enqueue("mastodon", "Cap", "https://r.example.com/mn", _PRODUCT)
        entries = rq._load()
        entries[0]["next_retry_at"] = time.time() - 1
        rq._save(entries)

        from api import pipeline
        monkeypatch.setattr(pipeline, "retry_queue", rq)

        with patch("api.pipeline.post_to_platform", AsyncMock(return_value=None)):
            result = await pipeline.retry_failed_posts()

        assert result["failed"] == 1
        # Still in queue (attempts went from 1 → 2, not at MAX yet)
        assert rq.queue_depth() == 1
