"""Amazon Associates product feed.

Appends the associate tag to Amazon product URLs and returns products
from a curated high-commission pool. When AMAZON_ASSOCIATE_TAG is set,
links earn 1-10% commission depending on category.

Category commission rates (Amazon Associates):
  Electronics: 2.5%  |  Beauty: 6%  |  Home: 8%  |  Fashion: 4%
  Books: 4.5%        |  Sports: 3%  |  Kitchen: 4.5%

Env: AMAZON_ASSOCIATE_TAG (e.g. "mysite-20")
"""

from __future__ import annotations

import os
import random
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

from ..utils import logger, metrics

_CATEGORY_COMMISSION = {
    "Electronics": 2.5,
    "Beauty": 6.0,
    "Home": 8.0,
    "Fashion": 4.0,
    "Books": 4.5,
    "Sports": 3.0,
    "Kitchen": 4.5,
    "Smart Home": 8.0,
    "Fitness": 3.0,
}

# Curated pool of high-performing Amazon products across top categories
# Commission rates are category defaults; actual rate depends on program agreement
PRODUCT_POOL: list[dict] = [
    # Beauty (6% commission)
    {"name": "CeraVe Moisturizing Cream 454g", "asin": "B00TTD9BRC",
     "price": 19.99, "category": "Beauty",
     "imageUrl": "https://m.media-amazon.com/images/I/51WtxXJDsNL._SL500_.jpg",
     "description": "Daily face and body moisturizer for dry skin. Developed with dermatologists."},
    {"name": "La Roche-Posay Anthelios SPF 60 Face Sunscreen", "asin": "B002CML1XE",
     "price": 33.99, "category": "Beauty",
     "imageUrl": "https://m.media-amazon.com/images/I/71JHk4ZFR+L._SL500_.jpg",
     "description": "Ultra-light facial sunscreen SPF 60. Ideal for sensitive and oily skin."},
    {"name": "Neutrogena Hydro Boost Gel Cream", "asin": "B00AQ7FL7K",
     "price": 24.97, "category": "Beauty",
     "imageUrl": "https://m.media-amazon.com/images/I/71BHKuVWb1L._SL500_.jpg",
     "description": "Hydrating gel cream with hyaluronic acid. Absorbs quickly without feeling greasy."},
    # Home (8% commission)
    {"name": "Instant Pot Duo 7-in-1 6Qt Electric Pressure Cooker", "asin": "B00FLYWNYQ",
     "price": 79.99, "category": "Kitchen",
     "imageUrl": "https://m.media-amazon.com/images/I/71V1chNfaUL._SL500_.jpg",
     "description": "7-in-1 multi-use cooker: pressure cooker, slow cooker, rice cooker, steamer, saute, yogurt maker, warmer."},
    {"name": "Dyson V15 Detect Absolute Cordless Vacuum", "asin": "B09FMQPK5J",
     "price": 749.99, "category": "Home",
     "imageUrl": "https://m.media-amazon.com/images/I/61E6qA5JNVL._SL500_.jpg",
     "description": "Laser detects dust on hard floors. Automatically adapts suction. HEPA filtration."},
    {"name": "Yankee Candle Large Jar — Clean Cotton", "asin": "B000JDGC36",
     "price": 31.99, "category": "Home",
     "imageUrl": "https://m.media-amazon.com/images/I/71RGP1uXz9L._SL500_.jpg",
     "description": "Authentic Yankee Candle scent. 110-150 hour burn time. Made in USA."},
    {"name": "AmazonBasics Microfiber Sheet Set Queen", "asin": "B01M0ATSJN",
     "price": 29.99, "category": "Home",
     "imageUrl": "https://m.media-amazon.com/images/I/71V2RNyK9pL._SL500_.jpg",
     "description": "Ultra-soft 1800 thread count microfiber. Wrinkle and fade resistant. 16-inch deep pockets."},
    # Electronics (2.5% commission, high ASP)
    {"name": "Apple AirPods Pro (2nd Generation) USB-C", "asin": "B0BDHWDR12",
     "price": 189.99, "category": "Electronics",
     "imageUrl": "https://m.media-amazon.com/images/I/61SUj2aKoEL._SL500_.jpg",
     "description": "Active Noise Cancellation, Transparency mode, Personalized Spatial Audio. MagSafe charging."},
    {"name": "Amazon Fire TV Stick 4K Max", "asin": "B09BKWGRFP",
     "price": 59.99, "category": "Electronics",
     "imageUrl": "https://m.media-amazon.com/images/I/51NoGjnFoML._SL500_.jpg",
     "description": "Supports Wi-Fi 6E. Streams in 4K Ultra HD with Dolby Vision and HDR10+."},
    {"name": "Anker 65W USB-C Charger (3-Port)", "asin": "B09C9WL6X5",
     "price": 35.99, "category": "Electronics",
     "imageUrl": "https://m.media-amazon.com/images/I/61oF18OFYML._SL500_.jpg",
     "description": "PowerIQ 3.0 fast charging. 2 USB-C + 1 USB-A ports. Foldable plug."},
    # Books (4.5% commission)
    {"name": "Atomic Habits by James Clear", "asin": "0735211299",
     "price": 16.99, "category": "Books",
     "imageUrl": "https://m.media-amazon.com/images/I/51B7kuFwQFL._SL500_.jpg",
     "description": "A proven framework for improving every day. #1 New York Times bestseller."},
    {"name": "The Psychology of Money by Morgan Housel", "asin": "0857197681",
     "price": 14.99, "category": "Books",
     "imageUrl": "https://m.media-amazon.com/images/I/71g2ednj0JL._SL500_.jpg",
     "description": "19 short stories exploring the weird ways people think about money and how to think better."},
    # Sports & Fitness (3%)
    {"name": "Resistance Bands Set (11-Piece) by Fit Simplify", "asin": "B01AVDVHTI",
     "price": 29.99, "category": "Sports",
     "imageUrl": "https://m.media-amazon.com/images/I/81T3RYJQ+UL._SL500_.jpg",
     "description": "5 resistance levels. Includes carrying case, door anchor, and exercise guide."},
    {"name": "Hydro Flask 32oz Wide Mouth Water Bottle", "asin": "B083SRBBWX",
     "price": 44.95, "category": "Sports",
     "imageUrl": "https://m.media-amazon.com/images/I/51E3MmQX6tL._SL500_.jpg",
     "description": "TempShield double-wall vacuum insulation. Keeps drinks cold 24 hours, hot 12 hours."},
]


def _tag() -> str:
    return os.environ.get("AMAZON_ASSOCIATE_TAG", "")


def _affiliate_url(asin: str) -> str:
    tag = _tag()
    base = f"https://www.amazon.com/dp/{asin}"
    if tag:
        return f"{base}?tag={tag}"
    return base


async def get_amazon_product() -> dict | None:
    """Return a curated Amazon product with affiliate link, or None if tag not configured."""
    tag = _tag()
    if not tag:
        logger.info("AMAZON_ASSOCIATE_TAG not set — Amazon feed disabled", "amazon")
        return None

    pool = list(PRODUCT_POOL)
    random.shuffle(pool)

    recent = metrics.get_recent_runs(200)
    posted_names = {r.get("product", "") for r in recent if r.get("success")}

    # Prefer unposted; fall back to any
    candidates = [p for p in pool if p["name"] not in posted_names] or pool

    product = candidates[0]
    asin = product.get("asin", "")
    commission_rate = _CATEGORY_COMMISSION.get(product.get("category", ""), 4.0)

    result = {
        "name": product["name"],
        "price": product.get("price"),
        "currency": "USD",
        "category": product.get("category", "General"),
        "description": product.get("description", ""),
        "imageUrl": product.get("imageUrl"),
        "deeplink": _affiliate_url(asin),
        "siteUrl": _affiliate_url(asin),
        "commissionRate": commission_rate,
        "source": "amazon",
        "asin": asin,
    }
    logger.info(f"Amazon product: {result['name']!r} @ ${result['price']} ({commission_rate}% commission)", "amazon")
    return result
