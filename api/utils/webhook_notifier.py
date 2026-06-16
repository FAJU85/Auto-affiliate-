import os
from datetime import datetime, timezone

import httpx


async def fire_webhook(url: str, payload: dict, timeout: float = 5.0) -> bool:
    """POST payload as JSON to url. Returns True on 2xx, False on any error."""
    if not url:
        return False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=timeout)
            return 200 <= response.status_code < 300
    except Exception:
        return False


async def notify_run_complete(result: dict) -> bool:
    """Fire webhook with run_complete event if WEBHOOK_URL env var is set."""
    url = os.environ.get("WEBHOOK_URL", "")
    if not url:
        return False
    payload = {
        "event": "run_complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    return await fire_webhook(url, payload)
