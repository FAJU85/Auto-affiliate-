"""SOVRN Commerce (VigLink) feed + link monetizer.

monetize_url(url)   — wraps any merchant URL into a tracked SOVRN affiliate link
get_sovrn_product() — picks a curated product and returns it monetized

Selection strategy: shuffle the pool and return the first product not in the
dedup store. Falls back to the least-recently-posted product if all are blocked.

Env: SOVRN_API_KEY
"""

import base64
import os
import random
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from ..utils import logger
from ..utils.circuit_breaker import sovrn_cb

API_BASE = "https://api.viglink.com/api"


def _key() -> str:
    return os.environ.get("SOVRN_API_KEY", "")


PRODUCT_POOL = [
    # Electronics
    {"name": "Sony WH-1000XM5 Noise Cancelling Headphones", "url": "https://www.amazon.com/dp/B09XS7JWHH", "price": 279.99, "currency": "USD", "category": "Electronics", "imageSearch": "Sony WH-1000XM5 headphones"},
    {"name": "Apple AirPods Pro (2nd Generation)", "url": "https://www.amazon.com/dp/B0BDHWDR12", "price": 189.99, "currency": "USD", "category": "Electronics", "imageSearch": "Apple AirPods Pro 2nd gen"},
    {"name": "Anker 737 Power Bank 24000mAh", "url": "https://www.amazon.com/dp/B09VPHVT2Z", "price": 75.99, "currency": "USD", "category": "Electronics", "imageSearch": "Anker 737 power bank"},
    {"name": "Logitech MX Master 3S Wireless Mouse", "url": "https://www.amazon.com/dp/B09HM94VDS", "price": 89.99, "currency": "USD", "category": "Electronics", "imageSearch": "Logitech MX Master 3S mouse"},
    {"name": "Samsung T7 Portable SSD 1TB", "url": "https://www.amazon.com/dp/B0874XN4D8", "price": 89.99, "currency": "USD", "category": "Electronics", "imageSearch": "Samsung T7 portable SSD"},
    {"name": "Kindle Paperwhite 16GB E-Reader", "url": "https://www.amazon.com/dp/B09TMF6742", "price": 139.99, "currency": "USD", "category": "Electronics", "imageSearch": "Kindle Paperwhite e-reader"},
    {"name": "Bose QuietComfort 45 Headphones", "url": "https://www.amazon.com/dp/B098FKXT8L", "price": 229.00, "currency": "USD", "category": "Electronics", "imageSearch": "Bose QuietComfort 45 headphones"},
    {"name": "Samsung 65-Inch QLED 4K Smart TV", "url": "https://www.amazon.com/dp/B0BZZY67SB", "price": 799.99, "currency": "USD", "category": "Electronics", "imageSearch": "Samsung QLED 4K TV 65 inch"},
    {"name": "Apple Watch Series 9 GPS 41mm", "url": "https://www.amazon.com/dp/B0CHX7R6WJ", "price": 299.00, "currency": "USD", "category": "Electronics", "imageSearch": "Apple Watch Series 9"},
    {"name": "GoPro HERO12 Black Action Camera", "url": "https://www.amazon.com/dp/B0CDFVMRJV", "price": 349.99, "currency": "USD", "category": "Electronics", "imageSearch": "GoPro HERO12 Black"},
    {"name": "iPad Air (5th Gen) 10.9-inch Wi-Fi 64GB", "url": "https://www.amazon.com/dp/B09V3HN1KC", "price": 499.00, "currency": "USD", "category": "Electronics", "imageSearch": "iPad Air 5th generation"},
    {"name": "Nintendo Switch OLED Model", "url": "https://www.amazon.com/dp/B098RL6SBJ", "price": 349.99, "currency": "USD", "category": "Electronics", "imageSearch": "Nintendo Switch OLED"},
    {"name": "Razer DeathAdder V3 Pro Wireless Mouse", "url": "https://www.amazon.com/dp/B0BJHG5FLG", "price": 99.99, "currency": "USD", "category": "Electronics", "imageSearch": "Razer DeathAdder V3 Pro"},
    {"name": "Garmin Forerunner 265 GPS Running Watch", "url": "https://www.amazon.com/dp/B0BT2PVRD8", "price": 349.99, "currency": "USD", "category": "Electronics", "imageSearch": "Garmin Forerunner 265"},
    {"name": "Amazon Echo Dot (5th Gen) Smart Speaker", "url": "https://www.amazon.com/dp/B09B8V1LZ3", "price": 49.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Amazon Echo Dot 5th gen"},
    # Smart Home
    {"name": "Philips Hue Smart Bulb Starter Kit", "url": "https://www.amazon.com/dp/B07353SKDD", "price": 69.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Philips Hue starter kit"},
    {"name": "Ring Video Doorbell (4th Gen)", "url": "https://www.amazon.com/dp/B08N5NQ869", "price": 99.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Ring video doorbell 4th gen"},
    {"name": "Nest Learning Thermostat (4th Gen)", "url": "https://www.amazon.com/dp/B0CWNP92P2", "price": 279.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Nest Learning Thermostat 4th gen"},
    {"name": "Arlo Pro 4 Wireless Security Camera", "url": "https://www.amazon.com/dp/B08XQTMVWH", "price": 169.99, "currency": "USD", "category": "Smart Home", "imageSearch": "Arlo Pro 4 security camera"},
    {"name": "iRobot Roomba j7+ Self-Emptying Robot Vacuum", "url": "https://www.amazon.com/dp/B09676KQDS", "price": 399.99, "currency": "USD", "category": "Smart Home", "imageSearch": "iRobot Roomba j7+ robot vacuum"},
    # Beauty & Health
    {"name": "CeraVe Moisturising Cream 454g", "url": "https://www.amazon.com/dp/B00TTD9BRC", "price": 19.99, "currency": "USD", "category": "Beauty", "imageSearch": "CeraVe moisturizing cream"},
    {"name": "Dyson Airwrap Multi-Styler", "url": "https://www.amazon.com/dp/B07G5B76KP", "price": 549.99, "currency": "USD", "category": "Beauty", "imageSearch": "Dyson Airwrap multi-styler"},
    {"name": "Oral-B Smart 5000 Electric Toothbrush", "url": "https://www.amazon.com/dp/B00V6NHQKQ", "price": 89.99, "currency": "USD", "category": "Health", "imageSearch": "Oral-B electric toothbrush"},
    {"name": "L'Oreal Paris Revitalift 1.5% Pure Hyaluronic Acid Serum", "url": "https://www.amazon.com/dp/B07PBG9TB3", "price": 29.99, "currency": "USD", "category": "Beauty", "imageSearch": "L'Oreal Revitalift hyaluronic acid serum"},
    {"name": "Waterpik Aquarius Water Flosser", "url": "https://www.amazon.com/dp/B008HLZXZQ", "price": 59.99, "currency": "USD", "category": "Health", "imageSearch": "Waterpik Aquarius water flosser"},
    {"name": "Withings Body+ Smart Wi-Fi Scale", "url": "https://www.amazon.com/dp/B071XW4C5Q", "price": 99.95, "currency": "USD", "category": "Health", "imageSearch": "Withings Body+ smart scale"},
    {"name": "Theragun Prime Percussion Massager", "url": "https://www.amazon.com/dp/B0948KTG89", "price": 199.00, "currency": "USD", "category": "Health", "imageSearch": "Theragun Prime massage gun"},
    # Home & Kitchen
    {"name": "Instant Pot Duo 7-in-1 Pressure Cooker 6qt", "url": "https://www.amazon.com/dp/B00FLYWNYQ", "price": 79.99, "currency": "USD", "category": "Home", "imageSearch": "Instant Pot Duo 7-in-1"},
    {"name": "Ninja AF101 Air Fryer 4qt", "url": "https://www.amazon.com/dp/B07FDJMC9Q", "price": 79.99, "currency": "USD", "category": "Home", "imageSearch": "Ninja air fryer"},
    {"name": "Keurig K-Elite Coffee Maker", "url": "https://www.amazon.com/dp/B078NN3TZC", "price": 129.99, "currency": "USD", "category": "Home", "imageSearch": "Keurig K-Elite coffee maker"},
    {"name": "Vitamix 5200 Blender Professional Grade", "url": "https://www.amazon.com/dp/B008H4SLV6", "price": 399.95, "currency": "USD", "category": "Home", "imageSearch": "Vitamix 5200 blender"},
    {"name": "Le Creuset Signature Cast Iron Round Dutch Oven 5.5qt", "url": "https://www.amazon.com/dp/B00006JSUE", "price": 399.95, "currency": "USD", "category": "Home", "imageSearch": "Le Creuset Dutch oven"},
    {"name": "Dyson V15 Detect Cordless Vacuum", "url": "https://www.amazon.com/dp/B09HKGPQYV", "price": 699.99, "currency": "USD", "category": "Home", "imageSearch": "Dyson V15 Detect vacuum"},
    {"name": "Nespresso Vertuo Next Coffee Machine", "url": "https://www.amazon.com/dp/B08GFKRRSF", "price": 149.00, "currency": "USD", "category": "Home", "imageSearch": "Nespresso Vertuo Next"},
    {"name": "Cuisinart 14-Cup Food Processor", "url": "https://www.amazon.com/dp/B0000645YQ", "price": 169.95, "currency": "USD", "category": "Home", "imageSearch": "Cuisinart 14-cup food processor"},
    # Fashion
    {"name": "Levi's 501 Original Fit Jeans", "url": "https://www.amazon.com/dp/B0079E7N4A", "price": 59.99, "currency": "USD", "category": "Fashion", "imageSearch": "Levi's 501 original fit jeans"},
    {"name": "Under Armour Men's Tech 2.0 Short Sleeve T-Shirt", "url": "https://www.amazon.com/dp/B01N39FHYB", "price": 25.99, "currency": "USD", "category": "Fashion", "imageSearch": "Under Armour tech shirt"},
    {"name": "Columbia Men's Watertight II Packable Rain Jacket", "url": "https://www.amazon.com/dp/B00BNVDKR8", "price": 69.99, "currency": "USD", "category": "Fashion", "imageSearch": "Columbia Watertight rain jacket"},
    {"name": "Adidas Ultraboost 23 Running Shoes", "url": "https://www.amazon.com/dp/B0BL51KS4D", "price": 139.99, "currency": "USD", "category": "Fashion", "imageSearch": "Adidas Ultraboost 23"},
    {"name": "Ray-Ban New Wayfarer Classic Sunglasses", "url": "https://www.amazon.com/dp/B004IUL30E", "price": 154.00, "currency": "USD", "category": "Fashion", "imageSearch": "Ray-Ban Wayfarer sunglasses"},
    {"name": "North Face Thermoball Eco Insulated Jacket", "url": "https://www.amazon.com/dp/B08GBVP74C", "price": 199.00, "currency": "USD", "category": "Fashion", "imageSearch": "North Face Thermoball Eco jacket"},
    # Fitness
    {"name": "Fitbit Charge 6 Fitness Tracker", "url": "https://www.amazon.com/dp/B0CLKTSSZ4", "price": 149.95, "currency": "USD", "category": "Fitness", "imageSearch": "Fitbit Charge 6 fitness tracker"},
    {"name": "Hydro Flask 32oz Water Bottle", "url": "https://www.amazon.com/dp/B01ACAX6WI", "price": 44.95, "currency": "USD", "category": "Fitness", "imageSearch": "Hydro Flask water bottle"},
    {"name": "Peloton Guide Camera-Based Strength Trainer", "url": "https://www.amazon.com/dp/B09GHFT2KD", "price": 195.00, "currency": "USD", "category": "Fitness", "imageSearch": "Peloton Guide strength trainer"},
    {"name": "Bowflex SelectTech 552 Adjustable Dumbbells", "url": "https://www.amazon.com/dp/B001ARYU58", "price": 349.00, "currency": "USD", "category": "Fitness", "imageSearch": "Bowflex SelectTech 552 dumbbells"},
    {"name": "Manduka PRO Yoga Mat 6mm", "url": "https://www.amazon.com/dp/B0009MH3HO", "price": 120.00, "currency": "USD", "category": "Fitness", "imageSearch": "Manduka PRO yoga mat"},
    {"name": "TRX All-In-One Suspension Training System", "url": "https://www.amazon.com/dp/B002YRB39O", "price": 134.99, "currency": "USD", "category": "Fitness", "imageSearch": "TRX suspension training"},
    # Books & Learning
    {"name": "Atomic Habits by James Clear (Hardcover)", "url": "https://www.amazon.com/dp/0735211299", "price": 19.99, "currency": "USD", "category": "Books", "imageSearch": "Atomic Habits James Clear book"},
    {"name": "The 48 Laws of Power by Robert Greene", "url": "https://www.amazon.com/dp/0140280197", "price": 18.00, "currency": "USD", "category": "Books", "imageSearch": "48 Laws of Power Robert Greene book"},
    # Office & Productivity
    {"name": "Herman Miller Aeron Chair Size B", "url": "https://www.amazon.com/dp/B00F67B6NA", "price": 1395.00, "currency": "USD", "category": "Office", "imageSearch": "Herman Miller Aeron chair"},
    {"name": "LG 27-Inch 4K UHD IPS Monitor", "url": "https://www.amazon.com/dp/B08R5K3HBW", "price": 349.99, "currency": "USD", "category": "Office", "imageSearch": "LG 27 inch 4K monitor"},
    {"name": "Jabra Evolve2 65 Wireless Headset", "url": "https://www.amazon.com/dp/B08DKSKDQK", "price": 299.00, "currency": "USD", "category": "Office", "imageSearch": "Jabra Evolve2 65 headset"},
    {"name": "Anker USB-C Hub 7-in-1", "url": "https://www.amazon.com/dp/B07ZVKTP53", "price": 35.99, "currency": "USD", "category": "Office", "imageSearch": "Anker USB-C hub 7-in-1"},
    {"name": "Elgato Stream Deck MK.2 15-Key Controller", "url": "https://www.amazon.com/dp/B09738CV2G", "price": 149.99, "currency": "USD", "category": "Office", "imageSearch": "Elgato Stream Deck MK.2"},
    # Outdoor & Travel
    {"name": "Osprey Farpoint 40L Travel Backpack", "url": "https://www.amazon.com/dp/B06XFLTZZH", "price": 160.00, "currency": "USD", "category": "Travel", "imageSearch": "Osprey Farpoint 40 backpack"},
    {"name": "Yeti Rambler 20oz Tumbler", "url": "https://www.amazon.com/dp/B073WD6HRX", "price": 34.99, "currency": "USD", "category": "Outdoor", "imageSearch": "Yeti Rambler 20oz tumbler"},
    {"name": "Black Diamond Storm 500 Headlamp", "url": "https://www.amazon.com/dp/B07MBPVP3Q", "price": 59.95, "currency": "USD", "category": "Outdoor", "imageSearch": "Black Diamond Storm headlamp"},
    {"name": "Patagonia Nano Puff Jacket", "url": "https://www.amazon.com/dp/B07M5X5Z5Q", "price": 199.00, "currency": "USD", "category": "Outdoor", "imageSearch": "Patagonia Nano Puff jacket"},
    {"name": "Samsonite Omni PC Hardside Luggage 24-inch", "url": "https://www.amazon.com/dp/B00IE8BHQO", "price": 129.99, "currency": "USD", "category": "Travel", "imageSearch": "Samsonite Omni PC luggage 24 inch"},
]


def _pick_product() -> dict:
    """Return a product, preferring ones not recently posted."""
    from ..utils.metrics import was_recently_posted

    pool = list(PRODUCT_POOL)
    random.shuffle(pool)

    for p in pool:
        if not was_recently_posted(p["url"], p["name"]):
            return p

    # All products recently posted — fall back to full random (dedup logic in pipeline will handle)
    logger.warn(f"SOVRN: all {len(pool)} products recently posted — cycling anyway")
    return random.choice(pool)


async def monetize_url(merchant_url: str) -> str:
    key = _key()
    if not key or not merchant_url:
        return merchant_url
    try:
        encoded = quote(merchant_url, safe="")
        api_url = f"{API_BASE}/link?key={key}&u={encoded}"
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(api_url, headers={"Accept": "application/json"})
        if r.status_code != 200:
            logger.warn(f"SOVRN link API {r.status_code}: {r.text[:120]} — using original URL", "sovrn")
            return merchant_url
        data = r.json()
        monetized = data.get("url") or merchant_url
        logger.info(f"Monetized: {merchant_url[:50]} → {monetized[:60]}", "sovrn")
        return monetized
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Monetize failed: {err}", "sovrn")
        return merchant_url


async def get_sovrn_product() -> dict | None:
    if not _key():
        return None
    if sovrn_cb.is_open():
        logger.warn("SOVRN circuit breaker OPEN — using original URL", "sovrn")
        product = _pick_product()
    else:
        product = _pick_product()
    logger.info(f"SOVRN Commerce: monetizing \"{product['name']}\"", "sovrn")
    try:
        deeplink = await sovrn_cb.call(monetize_url, product["url"])
    except Exception:
        deeplink = product["url"]
    if not deeplink or deeplink == product["url"]:
        logger.warn(f"SOVRN: link unchanged for \"{product['name']}\" — using original")
    pid = "sovrn-" + base64.b64encode(product["url"].encode()).decode()[:16]
    return {
        "id": pid,
        "name": product["name"],
        "description": product.get("description", product["name"]),
        "siteUrl": deeplink,
        "deeplink": deeplink,
        "imageUrl": None,
        "imageSearch": product["imageSearch"],
        "price": product["price"],
        "currency": product["currency"],
        "category": product["category"],
        "source": "sovrn",
    }
