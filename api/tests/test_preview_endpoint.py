"""Tests for POST /api/preview dry-run endpoint."""

import pytest
from httpx import AsyncClient, ASGITransport

from api.main import app


@pytest.mark.asyncio
async def test_preview_returns_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_preview_has_required_keys():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    data = r.json()
    for key in ("caption", "platform", "product_name", "category", "char_count", "dry_run"):
        assert key in data


@pytest.mark.asyncio
async def test_preview_dry_run_is_true():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    assert r.json()["dry_run"] is True


@pytest.mark.asyncio
async def test_preview_char_count_matches():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    data = r.json()
    assert data["char_count"] == len(data["caption"])


@pytest.mark.asyncio
async def test_preview_default_platform_is_bluesky():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    assert r.json()["platform"] == "bluesky"


@pytest.mark.asyncio
async def test_preview_custom_platform():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones", "platform": "mastodon"})
    assert r.json()["platform"] == "mastodon"


@pytest.mark.asyncio
async def test_preview_caption_is_nonempty_string():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    caption = r.json()["caption"]
    assert isinstance(caption, str) and len(caption) > 0


@pytest.mark.asyncio
async def test_preview_product_name_reflected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Test Widget"})
    assert r.json()["product_name"] == "Test Widget"


@pytest.mark.asyncio
async def test_preview_minimal_body():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["product_name"] == "Sample Product"


@pytest.mark.asyncio
async def test_preview_category_auto_detected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/preview", json={"name": "Sony Headphones"})
    data = r.json()
    assert isinstance(data["category"], str) and len(data["category"]) > 0
