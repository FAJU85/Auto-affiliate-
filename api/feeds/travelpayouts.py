"""Travelpayouts flight deals feed (Aviasales API).

Picks a random origin from a pool of major cities, fetches the cheapest
available flights for the year, and returns the deal as a normalised product.

Env:
  TRAVELPAYOUTS_TOKEN  — API access token (required)
  TRAVELPAYOUTS_MARKER — partner marker number from Travelpayouts dashboard
                         (falls back to TOKEN if not set; links may not track)
"""

import os
import random
from datetime import date

import httpx

from ..utils import logger

API_BASE = "https://api.travelpayouts.com"

ORIGINS = [
    "NYC", "LON", "PAR", "DXB", "SIN", "LAX", "BKK",
    "IST", "SYD", "TYO", "GRU", "JNB", "CDG", "AMS", "FCO", "MEX",
]


def _token() -> str:
    return os.environ.get("TRAVELPAYOUTS_TOKEN", "")


def _marker() -> str:
    return os.environ.get("TRAVELPAYOUTS_MARKER", "") or _token()


async def _fetch_deals(token: str, origin: str) -> list[dict]:
    url = (
        f"{API_BASE}/v2/prices/latest"
        f"?currency=usd&origin={origin}&limit=10"
        f"&show_to_affiliates=true&sorting=price&period_type=year"
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, headers={"X-Access-Token": token, "Accept": "application/json"})
        if r.status_code != 200:
            logger.warn(f"Travelpayouts API {r.status_code} for {origin}: {r.text[:200]}", "travelpayouts")
            return []
        data = r.json()
        return data.get("data") or []
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Travelpayouts fetch error ({origin}): {err}", "travelpayouts")
        return []


def _build_product(deal: dict, origin: str, marker: str) -> dict | None:
    destination = deal.get("destination")
    if not destination:
        return None
    price = deal.get("value")
    airline = deal.get("airline", "")
    departs = deal.get("depart_date", "")

    # General route URL — always shows results; date-specific redirects to homepage
    site_url = f"https://www.aviasales.com/{origin}-{destination}/?marker={marker}"

    name = f"Flight {origin} → {destination}" + (f" ({airline})" if airline else "")
    desc = (
        f"From ${price}. Fly {origin} to {destination}"
        + (f" departing {departs}" if departs else "")
        + "."
    )

    today = date.today().isoformat()
    return {
        "id": f"tp-{origin}-{destination}-{today}",
        "name": name,
        "description": desc,
        "siteUrl": site_url,
        "deeplink": site_url,
        "imageUrl": None,
        "imageSearch": f"flight {origin} {destination} airplane travel",
        "price": float(price) if price else None,
        "currency": "USD",
        "commissionRate": 0,
        "category": "Travel",
        "source": "travelpayouts",
    }


async def get_travelpayouts_product() -> dict | None:
    token = _token()
    if not token:
        return None

    marker = _marker()
    logger.info("Fetching Travelpayouts flight deals…", "travelpayouts")

    # Try up to 3 random origins — some may return no results
    shuffled = random.sample(ORIGINS, min(3, len(ORIGINS)))
    for origin in shuffled:
        deals = await _fetch_deals(token, origin)
        logger.info(f"Travelpayouts: {len(deals)} deals from {origin}", "travelpayouts")
        if deals:
            picked = random.choice(deals[:5])
            product = _build_product(picked, origin, marker)
            if product:
                return product

    logger.warn("Travelpayouts: no deals found for any sampled origin", "travelpayouts")
    return None
