"""Admitad XML product feed.

Streams the XML feed URL (ADMITAD_FEED_URL), parses <offer> blocks, filters
for English-language products with images, and returns a random high-commission
product as a normalised dict.

No OAuth required — the feed URL already contains auth parameters and the
<url> inside each offer is a pre-built deeplink.

Env: ADMITAD_FEED_URL
"""

import html
import os
import re

import httpx

from ..utils import logger

_NON_LATIN = re.compile(r"[^ -ɏ\s\d\W]", re.UNICODE)
MAX_FEED_BYTES = 2 * 1024 * 1024  # 2 MB — enough for hundreds of offers


def _is_english(text: str) -> bool:
    if not text or len(text) < 3:
        return True
    non_latin = len(_NON_LATIN.findall(text))
    return non_latin / len(text) < 0.4


def _tag(body: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", body, re.DOTALL | re.IGNORECASE)
    return html.unescape(m.group(1).strip()) if m else ""


def _param(body: str, name: str) -> str:
    m = re.search(
        rf'<param\s+name="{re.escape(name)}"[^>]*>(.*?)</param>',
        body, re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _parse_offer(offer_id: str, body: str) -> dict | None:
    name = _tag(body, "name")
    url = _tag(body, "url")
    if not url or not name:
        return None
    if not _is_english(name):
        return None
    try:
        # Basic URL sanity check
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return None
    except Exception:
        return None

    price_str = _tag(body, "price")
    price = float(price_str) if price_str else None
    currency = _tag(body, "currencyId") or "USD"
    description = (_tag(body, "description") or name).strip()
    image_url = _tag(body, "picture") or None
    commission_rate = float(_param(body, "commissionRate") or "0")
    category = _tag(body, "categoryId") or _param(body, "category") or None

    return {
        "id": offer_id,
        "name": name.strip(),
        "description": description[:300],
        "siteUrl": url.strip(),
        "deeplink": url.strip(),
        "imageUrl": image_url,
        "imageSearch": name.strip(),
        "price": price,
        "currency": currency,
        "commissionRate": commission_rate,
        "category": category,
        "source": "admitad",
    }


def _parse_offers(xml: str) -> list[dict]:
    offers = []
    pattern = re.compile(r'<offer\s[^>]*id="([^"]*)"[^>]*>([\s\S]*?)</offer>')
    for m in pattern.finditer(xml):
        try:
            offer = _parse_offer(m.group(1), m.group(2))
            if offer:
                offers.append(offer)
        except Exception:
            pass
    return offers


async def get_admitad_product() -> dict | None:
    feed_url = os.environ.get("ADMITAD_FEED_URL", "")
    if not feed_url:
        return None

    logger.info("Fetching Admitad XML feed…", "admitad")
    xml_chunks: list[bytes] = []
    total = 0
    aborted = False

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            async with client.stream("GET", feed_url) as r:
                if r.status_code != 200:
                    logger.warn(f"Admitad feed HTTP {r.status_code}", "admitad")
                    return None
                async for chunk in r.aiter_bytes(chunk_size=65536):
                    xml_chunks.append(chunk)
                    total += len(chunk)
                    if total >= MAX_FEED_BYTES:
                        aborted = True
                        break
    except Exception as err:  # noqa: BLE001
        if not xml_chunks:
            logger.warn(f"Admitad feed fetch failed: {err}", "admitad")
            return None
        # Partial data — continue with what we have
        logger.warn(f"Admitad feed truncated after {total} bytes: {err}", "admitad")

    xml = b"".join(xml_chunks).decode("utf-8", errors="replace")
    if aborted:
        logger.info(f"Admitad feed capped at {MAX_FEED_BYTES // 1024}KB", "admitad")

    offers = _parse_offers(xml)
    logger.info(f"Admitad: parsed {len(offers)} offers", "admitad")
    if not offers:
        return None

    # Prefer offers with images, then by commission
    with_image = [o for o in offers if o["imageUrl"]]
    pool = with_image if with_image else offers
    with_commission = [o for o in pool if o["commissionRate"] > 0]
    candidates = with_commission if with_commission else pool

    import random
    random.shuffle(candidates)
    picked = candidates[0]
    logger.info(
        f"Admitad selected: {picked['name']!r} "
        f"(image: {bool(picked['imageUrl'])}, commission: {picked['commissionRate']}%)",
        "admitad",
    )
    return picked
