"""SOVRN Commerce (VigLink) feed + link monetizer.

monetize_url(url)   — wraps any merchant URL into a tracked SOVRN affiliate link
get_sovrn_product() — picks a curated product and returns it monetized

Env: SOVRN_API_KEY
"""

import base64
import os
import random
from urllib.parse import quote

import httpx

from ..utils import logger

API_BASE = "https://api.viglink.com/api"


def _key() -> str:
    return os.environ.get("SOVRN_API_KEY", "")


PRODUCT_POOL = [
    {"name": "Sony WH-1000XM5 Noise Cancelling Headphones", "url": "https://www.amazon.com/dp/B09XS7JWHH", "price": 279.99, "currency": "USD", "category": "Electronics", "imageSearch": "Sony WH-1000XM5 headphones"},
    {"name": "Apple AirPods Pro (2nd Generation)", "url": "https://www.amazon.com/dp/B0BDHWDR12", "price": 189.99, "currency": "USD", "category": "Electronics", "imageSearch": "Apple AirPods Pro 2nd gen"},
    {"name": "Anker 737 Power Bank 24000mAh", "url": "https://www.amazon.com/dp/B09VPHVT2Z", "price": 75.99, "currency": "USD", "category": "Electronics", "imageSearch": "Anker 737 power bank"},
    {"name": "Logitech MX Master 3S Wireless Mouse", "url": "https://www.amazon.com/dp/B09HM94VDS", "price": 89.99, "currency": "USD", "category": "Electronics", "imageSearch": "Logitech MX Master 3S mouse"},
    {"name": "Samsung T7 Portable SSD 1TB", "url": "https://www.amazon.com/dp/B0874XN4D8", "price": 89.99, "currency": "USD", "category": "Electronics", "imageSearch": "Samsung T7 portable SSD"},
    {"name": "Kindle Paperwhite 16GB E-Reader", "url": "https://www.amazon.com/dp/B09TMF6742", "price": 139.99, "currency": "USD", "category": "Electronics", "imageSearch": "Kindle Paperwhite e-reader"},
    {"name": "Philips Hue Smart Bulb Starter Kit", "url": "https://www.amazon.com/dp/B07353SKDD", "price": 69.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Philips Hue starter kit"},
    {"name": "CeraVe Moisturising Cream 454g", "url": "https://www.amazon.com/dp/B00TTD9BRC", "price": 19.99, "currency": "USD", "category": "Beauty", "imageSearch": "CeraVe moisturizing cream"},
    {"name": "Dyson Airwrap Multi-Styler", "url": "https://www.amazon.com/dp/B07G5B76KP", "price": 549.99, "currency": "USD", "category": "Beauty", "imageSearch": "Dyson Airwrap multi-styler"},
    {"name": "Oral-B Smart 5000 Electric Toothbrush", "url": "https://www.amazon.com/dp/B00V6NHQKQ", "price": 89.99, "currency": "USD", "category": "Health", "imageSearch": "Oral-B electric toothbrush"},
    {"name": "Instant Pot Duo 7-in-1 Pressure Cooker 6qt", "url": "https://www.amazon.com/dp/B00FLYWNYQ", "price": 79.99, "currency": "USD", "category": "Home", "imageSearch": "Instant Pot Duo 7-in-1"},
    {"name": "Ninja AF101 Air Fryer 4qt", "url": "https://www.amazon.com/dp/B07FDJMC9Q", "price": 79.99, "currency": "USD", "category": "Home", "imageSearch": "Ninja air fryer"},
    {"name": "Ring Video Doorbell (4th Gen)", "url": "https://www.amazon.com/dp/B08N5NQ869", "price": 99.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Ring video doorbell 4th gen"},
    {"name": "Levi's 501 Original Fit Jeans", "url": "https://www.amazon.com/dp/B0079E7N4A", "price": 59.99, "currency": "USD", "category": "Fashion", "imageSearch": "Levi's 501 original fit jeans"},
    {"name": "Under Armour Men's Tech 2.0 Short Sleeve T-Shirt", "url": "https://www.amazon.com/dp/B01N39FHYB", "price": 25.99, "currency": "USD", "category": "Fashion", "imageSearch": "Under Armour tech shirt"},
    {"name": "Fitbit Charge 6 Fitness Tracker", "url": "https://www.amazon.com/dp/B0CLKTSSZ4", "price": 149.95, "currency": "USD", "category": "Fitness", "imageSearch": "Fitbit Charge 6 fitness tracker"},
    {"name": "Hydro Flask 32oz Water Bottle", "url": "https://www.amazon.com/dp/B01ACAX6WI", "price": 44.95, "currency": "USD", "category": "Fitness", "imageSearch": "Hydro Flask water bottle"},
]


async def monetize_url(merchant_url: str) -> str:
    key = _key()
    if not key or not merchant_url:
        return merchant_url
    try:
        encoded = quote(merchant_url, safe="")
        api_url = f"{API_BASE}/link?key={key}&u={encoded}&ref=https%3A%2F%2Fbluesky.app"
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(api_url, headers={"Accept": "application/json"})
        if r.status_code != 200:
            logger.warn(f"SOVRN link API {r.status_code} for {merchant_url[:60]}")
            return merchant_url
        data = r.json()
        monetized = data.get("url") or merchant_url
        logger.info(f"SOVRN monetized: {merchant_url[:50]} -> {monetized[:60]}")
        return monetized
    except Exception as err:  # noqa: BLE001
        logger.warn(f"SOVRN monetize failed: {err}")
        return merchant_url


async def get_sovrn_product() -> dict | None:
    if not _key():
        return None
    product = random.choice(PRODUCT_POOL)
    logger.info(f"SOVRN Commerce: monetizing \"{product['name']}\"")
    deeplink = await monetize_url(product["url"])
    if not deeplink or deeplink == product["url"]:
        logger.warn(f"SOVRN: link unchanged for \"{product['name']}\" — using original")
    pid = "sovrn-" + base64.b64encode(product["url"].encode()).decode()[:16]
    return {
        "id": pid,
        "name": product["name"],
        "description": product["name"],
        "siteUrl": deeplink,
        "deeplink": deeplink,
        "imageUrl": None,
        "imageSearch": product["imageSearch"],
        "price": product["price"],
        "currency": product["currency"],
        "category": product["category"],
        "source": "sovrn",
    }
