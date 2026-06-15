"""
Session-start QA hook + test isolation fixtures.

When pytest collects test_qa_suite.py (e.g. `make qa`), the banner below
reminds that this suite is the first gate — all 95 tests must be green
before any feature work proceeds.

APScheduler isolation
─────────────────────
The module-level AsyncIOScheduler in api/main.py is a singleton.  Each
module-scoped TestClient(app) starts its own anyio event loop via the ASGI
lifespan.  When the ``with TestClient(...)`` block exits the loop is closed;
APScheduler then holds a reference to that dead loop.  The next TestClient
creates a *new* loop and tries to start the same scheduler — producing either
``SchedulerAlreadyRunningError`` or ``RuntimeError: Event loop is closed``.

Fix: wrap start/shutdown so the scheduler cleanly detaches from a dead loop
and re-attaches to the current one on each TestClient startup.
"""
import asyncio
import pytest


def pytest_collection_finish(session):
    qa_items = [i for i in session.items if "test_qa_suite" in str(i.fspath)]
    if qa_items:
        print(
            f"\n{'='*60}\n"
            f"  QA AUTOMATION SUITE  —  {len(qa_items)} session-start checks\n"
            f"  All must pass before feature work begins.\n"
            f"{'='*60}\n"
        )


@pytest.fixture(scope="session", autouse=True)
def patch_scheduler():
    """Make AsyncIOScheduler lifecycle safe across multiple TestClient instances.

    Each TestClient creates its own anyio event loop.  We intercept start/shutdown
    to:
    - shutdown: fully stop the scheduler and clear its event-loop reference
    - start: clear any stale loop reference so APScheduler picks up the new loop
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.base import SchedulerAlreadyRunningError

    original_start = AsyncIOScheduler.start
    original_shutdown = AsyncIOScheduler.shutdown

    def safe_start(self, *args, **kwargs):
        # Clear stale loop reference so APScheduler picks up the current loop
        if hasattr(self, '_eventloop') and self._eventloop is not None:
            try:
                if self._eventloop.is_closed():
                    self._eventloop = None
                    self._state = 0  # STATE_STOPPED
            except Exception:
                self._eventloop = None
                self._state = 0

        if self.running:
            return
        try:
            original_start(self, *args, **kwargs)
        except (SchedulerAlreadyRunningError, RuntimeError):
            pass

    def safe_shutdown(self, wait=True, **kwargs):
        if not self.running:
            return
        try:
            original_shutdown(self, wait=False)
        except Exception:
            pass
        # Clear the event-loop reference so next start picks up the new loop
        try:
            self._eventloop = None
        except Exception:
            pass

    AsyncIOScheduler.start = safe_start
    AsyncIOScheduler.shutdown = safe_shutdown
    yield
    AsyncIOScheduler.start = original_start
    AsyncIOScheduler.shutdown = original_shutdown
