import asyncio

import httpx


async def check_link(url: str, timeout: float = 5.0) -> dict:
    if not url:
        return {"url": url, "status_code": None, "alive": False, "redirect_url": None, "error": "empty url"}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.head(url)
        redirect_url = str(r.url) if str(r.url) != url else None
        return {
            "url": url,
            "status_code": r.status_code,
            "alive": r.status_code < 400,
            "redirect_url": redirect_url,
            "error": None,
        }
    except Exception as e:  # noqa: BLE001
        return {"url": url, "status_code": None, "alive": False, "redirect_url": None, "error": str(e)}


async def check_links_batch(urls: list[str], timeout: float = 5.0) -> list[dict]:
    return list(await asyncio.gather(*[check_link(u, timeout) for u in urls]))


def filter_alive_products(products: list[dict], results: list[dict]) -> list[dict]:
    return [p for p, r in zip(products, results) if r.get("alive")]
