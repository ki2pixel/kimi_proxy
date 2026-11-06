"""Tests de robustesse réseau du client proxy."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from kimi_proxy.proxy.client import create_proxy_client


@pytest.mark.asyncio
async def test_client_retry_on_read_error():
    """Le client retry sur ReadError puis réussit."""
    client = create_proxy_client(max_retries=2, retry_delay=0.01)

    call_count = 0

    async def mock_send(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ReadError("First call fails")

        response = MagicMock()
        response.status_code = 200
        response.json = MagicMock(return_value={"ok": True})
        return response

    with patch("httpx.AsyncClient.send", side_effect=mock_send):
        with patch("httpx.AsyncClient.aclose", new_callable=AsyncMock):
            req = client.build_request("POST", "https://api.test.com", {}, "{}")
            response = await client.send(req)

    assert response.status_code == 200
    assert call_count == 2
