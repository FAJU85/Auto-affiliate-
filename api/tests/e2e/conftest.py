"""Playwright E2E fixtures.

Starts the FastAPI app in a background thread, waits for it to be ready,
then hands each test a Playwright page pointed at it.
"""

import threading
import time

import pytest
import uvicorn
from playwright.sync_api import sync_playwright


def _find_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url(tmp_path_factory):
    """Spin up the FastAPI app on a random port; yield its base URL."""
    import os
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["DATA_DIR"] = str(data_dir)

    from api.main import app

    port = _find_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait up to 5s for the server to be ready
    base = f"http://127.0.0.1:{port}"
    import httpx
    for _ in range(50):
        try:
            httpx.get(f"{base}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    yield base

    server.should_exit = True
    thread.join(timeout=3)


@pytest.fixture(scope="session")
def browser_context(live_server_url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context, live_server_url):
    p = browser_context.new_page()
    p.goto(live_server_url, wait_until="domcontentloaded")
    yield p
    p.close()
