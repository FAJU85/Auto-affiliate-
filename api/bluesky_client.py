"""Bluesky posting via the atproto library (app-password login).

Env: BSKY_HANDLE, BSKY_APP_PASSWORD
"""

import asyncio
import os

from atproto import Client, models

from .utils import logger

GRAPHEME_LIMIT = 300


def _truncate(text: str, deeplink: str) -> str:
    """Keep total under GRAPHEME_LIMIT, always preserving the deeplink."""
    suffix = "\n" + deeplink if deeplink else ""
    budget = GRAPHEME_LIMIT - len(suffix)
    body = text.strip()
    if len(body) > budget:
        body = body[: max(0, budget - 1)].rstrip() + "…"
    return body + suffix


def _link_facets(full_text: str, deeplink: str) -> list | None:
    if not deeplink:
        return None
    raw = full_text.encode("utf-8")
    target = deeplink.encode("utf-8")
    start = raw.find(target)
    if start < 0:
        return None
    return [
        models.AppBskyRichtextFacet.Main(
            index=models.AppBskyRichtextFacet.ByteSlice(
                byte_start=start, byte_end=start + len(target)
            ),
            features=[models.AppBskyRichtextFacet.Link(uri=deeplink)],
        )
    ]


def _build_embed(client: Client, image_bytes: bytes | None, product: dict):
    if not image_bytes:
        return None
    try:
        upload = client.upload_blob(image_bytes)
        alt = product.get("name", "Product image")[:280]
        return models.AppBskyEmbedImages.Main(
            images=[models.AppBskyEmbedImages.Image(alt=alt, image=upload.blob)]
        )
    except Exception as err:  # noqa: BLE001
        logger.warn(f"Bluesky image upload failed: {err}")
        return None


def _post_sync(text: str, deeplink: str, image_bytes: bytes | None, product: dict) -> str:
    handle = os.environ.get("BSKY_HANDLE", "")
    password = os.environ.get("BSKY_APP_PASSWORD", "")
    if not handle or not password:
        raise RuntimeError("BSKY_HANDLE / BSKY_APP_PASSWORD not configured")

    client = Client()
    client.login(handle, password)

    full_text = _truncate(text, deeplink)
    facets = _link_facets(full_text, deeplink)
    embed = _build_embed(client, image_bytes, product)

    response = client.send_post(text=full_text, facets=facets, embed=embed)
    logger.info(f"Posted to Bluesky: {response.uri}")
    return response.uri


async def post_to_bluesky(
    text: str, deeplink: str, image_bytes: bytes | None, product: dict
) -> str:
    return await asyncio.to_thread(_post_sync, text, deeplink, image_bytes, product)
