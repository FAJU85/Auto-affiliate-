"""TakeAds affiliate network feed.

Fetches active programs sorted by average commission, picks a top-10 random
selection, resolves a tracking link, and returns a normalised product dict.

Env: TAKEADS_API_KEY
"""

import os
import re
import time

import httpx

from ..utils import logger
from ..utils.circuit_breaker import CircuitBreaker

takeads_cb = CircuitBreaker("takeads", failure_threshold=3, recovery_timeout=120)

API_BASE = "https://api.takeads.com/v3"
_NON_LATIN = re.compile(r"[^ -ɏ\s\d\W]", re.UNICODE)


def _key() -> str:
    return os.environ.get("TAKEADS_API_KEY", "")


def _is_english(name: str) -> bool:
    if not name or len(name) < 3:
        return True
    non_latin = len(_NON_LATIN.findall(name))
    return non_latin / len(name) < 0.4


async def _fetch_programs(api_key: str) -> list[dict]:
    """Try /v3/programs then /v3/program (legacy) — API path changed between versions."""
    query = "?limit=50&programStatus=active&sortBy=avgCommission&sortOrder=desc"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    for path in ("/programs", "/program"):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API_BASE}{path}{query}", headers=headers)
        if r.status_code == 404:
            logger.warn(f"TakeAds {path} returned 404 — trying next path", "takeads")
            continue
        if r.status_code != 200:
            raise RuntimeError(f"TakeAds programs API {r.status_code}: {r.text[:200]}")
        data = r.json()
        logger.info(f"TakeAds: fetched programs via {path}", "takeads")
        return data.get("data") or []
    raise RuntimeError("TakeAds: all program endpoints returned 404")


async def _resolve_link(api_key: str, url: str) -> str | None:
    """Create an affiliate tracking link. Tries POST /links then PUT /resolve."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {"iris": [url], "subId": f"auto-{int(time.time())}", "withImages": False}
    for method, path in [("POST", "/links"), ("PUT", "/resolve")]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.request(method, f"{API_BASE}{path}", headers=headers, json=body)
            if not r.is_success:
                logger.warn(f"TakeAds {method} {path} → {r.status_code}", "takeads")
                continue
            data = r.json()
            items = data.get("data") or data.get("items") or []
            if items and isinstance(items, list):
                link = items[0].get("trackingLink") or items[0].get("url")
                if link:
                    return link
        except Exception as err:  # noqa: BLE001
            logger.warn(f"TakeAds resolve {method} {path} failed: {err}", "takeads")
    return None


async def _fetch() -> dict | None:
    api_key = _key()
    if not api_key:
        return None

    programs_raw = await _fetch_programs(api_key)
    programs = [
        p for p in programs_raw
        if p.get("websiteUrl") and (p.get("avgCommission") or 0) > 0
        and _is_english(str(p.get("name") or ""))
    ]
    if not programs:
        logger.warn("TakeAds: no suitable programs after filtering", "takeads")
        return None

    programs.sort(key=lambda p: float(p.get("avgCommission") or 0), reverse=True)
    import random
    program = random.choice(programs[:10])
    logger.info(
        f"TakeAds program: {program.get('name')!r} "
        f"(avgCommission: {program.get('avgCommission')})",
        "takeads",
    )

    tracking_link = await _resolve_link(api_key, program["websiteUrl"])
    name = str(program.get("name") or "").strip()
    description = (
        program.get("description") or program.get("shortDescription") or name
    ).strip()[:300]

    return {
        "id": str(program.get("id") or program.get("merchantId") or ""),
        "name": name,
        "description": description,
        "siteUrl": tracking_link or program["websiteUrl"],
        "deeplink": tracking_link or program["websiteUrl"],
        "imageUrl": program.get("imageUrl") or program.get("logoUrl"),
        "imageSearch": name,
        "price": None,
        "currency": "USD",
        "commissionRate": float(program.get("avgCommission") or 0),
        "category": program.get("category") or program.get("verticalName"),
        "source": "takeads",
    }


async def get_takeads_product() -> dict | None:
    if not _key():
        return None
    if takeads_cb.is_open():
        logger.warn("TakeAds circuit breaker OPEN — skipping", "takeads")
        return None
    try:
        return await takeads_cb.call(_fetch)
    except Exception as err:  # noqa: BLE001
        logger.warn(f"TakeAds fetch failed: {err}", "takeads")
        return None
