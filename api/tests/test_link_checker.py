from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_check_link_returns_required_keys():
    from api.utils.link_checker import check_link
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example.com/product"
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link("https://example.com/product")
    for key in ("url", "status_code", "alive", "redirect_url", "error"):
        assert key in result


@pytest.mark.asyncio
async def test_check_link_alive_on_200():
    from api.utils.link_checker import check_link
    mock_resp = MagicMock(status_code=200, url="https://example.com/product")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link("https://example.com/product")
    assert result["alive"] is True
    assert result["error"] is None


@pytest.mark.asyncio
async def test_check_link_alive_on_301():
    from api.utils.link_checker import check_link
    mock_resp = MagicMock(status_code=301, url="https://example.com/new")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link("https://example.com/old")
    assert result["alive"] is True


@pytest.mark.asyncio
async def test_check_link_dead_on_404():
    from api.utils.link_checker import check_link
    mock_resp = MagicMock(status_code=404, url="https://example.com/gone")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link("https://example.com/gone")
    assert result["alive"] is False


@pytest.mark.asyncio
async def test_check_link_dead_on_exception():
    from api.utils.link_checker import check_link
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(side_effect=Exception("connection refused"))
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link("https://example.com/product")
    assert result["alive"] is False
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_check_link_empty_url():
    from api.utils.link_checker import check_link
    result = await check_link("")
    assert result["alive"] is False
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_check_links_batch_returns_same_length():
    from api.utils.link_checker import check_links_batch
    mock_resp = MagicMock(status_code=200, url="https://example.com/a")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        results = await check_links_batch(["https://a.com", "https://b.com", "https://c.com"])
    assert len(results) == 3


@pytest.mark.asyncio
async def test_check_links_batch_empty():
    from api.utils.link_checker import check_links_batch
    results = await check_links_batch([])
    assert results == []


def test_filter_alive_products_keeps_alive():
    from api.utils.link_checker import filter_alive_products
    products = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
    results = [{"alive": True}, {"alive": False}, {"alive": True}]
    filtered = filter_alive_products(products, results)
    assert len(filtered) == 2
    assert filtered[0]["name"] == "A"
    assert filtered[1]["name"] == "C"


def test_filter_alive_products_empty():
    from api.utils.link_checker import filter_alive_products
    assert filter_alive_products([], []) == []


@pytest.mark.asyncio
async def test_check_link_sets_redirect_url():
    from api.utils.link_checker import check_link
    mock_resp = MagicMock(status_code=200, url="https://example.com/redirected")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link("https://example.com/original")
    assert result["redirect_url"] == "https://example.com/redirected"


@pytest.mark.asyncio
async def test_check_link_no_redirect_when_same_url():
    from api.utils.link_checker import check_link
    url = "https://example.com/product"
    mock_resp = MagicMock(status_code=200, url=url)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.head = AsyncMock(return_value=mock_resp)
    with patch("api.utils.link_checker.httpx.AsyncClient", return_value=mock_client):
        result = await check_link(url)
    assert result["redirect_url"] is None
