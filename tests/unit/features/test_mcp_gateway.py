from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from kimi_proxy.api.routes import mcp_gateway
from kimi_proxy.features.mcp.gateway import MCPGatewayService


def test_apply_observation_masking_truncates_large_string():
    service = MCPGatewayService()
    text = "A" * 10_000
    masked = service.apply_observation_masking(text)
    assert isinstance(masked, str)
    assert "KIMI_PROXY_OBSERVATION_MASKED" in masked
    assert masked.startswith("A" * 2000)
    assert masked.endswith("A" * 2000)
    assert "original_chars=10000" in masked


def test_apply_observation_masking_nested_structure():
    service = MCPGatewayService()
    payload: object = {
        "items": ["B" * 9000, {"inner": "C" * 8000}],
        "ok": "short",
    }
    masked = service.apply_observation_masking(payload)
    assert isinstance(masked, dict)
    items = masked.get("items")
    assert isinstance(items, list)
    assert isinstance(items[0], str)
    assert "KIMI_PROXY_OBSERVATION_MASKED" in items[0]
    assert isinstance(items[1], dict)
    assert "KIMI_PROXY_OBSERVATION_MASKED" in str(items[1].get("inner"))
    assert masked.get("ok") == "short"


def test_build_jsonrpc_error_preserves_id():
    service = MCPGatewayService()
    req: object = {"jsonrpc": "2.0", "method": "x", "params": {}, "id": 42}
    err = service.build_jsonrpc_error(req, code=-32001, message="oops", data={"x": 1})
    assert err["jsonrpc"] == "2.0"
    assert err["id"] == 42
    assert isinstance(err["error"], dict)
    assert err["error"]["code"] == -32001
    assert err["error"]["message"] == "oops"
    assert err["error"]["data"] == {"x": 1}


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_gateway.router, prefix="/api")
    return app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_gateway_unknown_server_returns_jsonrpc_error(async_client: httpx.AsyncClient):
    req = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": "req-1"}
    resp = await async_client.post("/api/mcp-gateway/unknown/rpc", json=req)
    assert resp.status_code == 404
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-1"
    assert body["error"]["code"] == -32001


@pytest.mark.asyncio
async def test_gateway_upstream_timeout_returns_jsonrpc_error(monkeypatch, async_client: httpx.AsyncClient):
    class _FakeTimeoutClient:
        async def __aenter__(self) -> _FakeTimeoutClient:
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            return None

        async def post(self, url: str, **kwargs) -> httpx.Response:
            raise httpx.TimeoutException("Timeout")

    def _fake_async_client(*args, **kwargs) -> _FakeTimeoutClient:
        return _FakeTimeoutClient()

    # ⚠️ Important: patch only the Proxy layer's AsyncClient symbol to avoid
    # impacting the httpx.AsyncClient used by the ASGI test client.
    import kimi_proxy.proxy.mcp_gateway_rpc as mcp_gateway_rpc

    monkeypatch.setattr(mcp_gateway_rpc.httpx, "AsyncClient", _fake_async_client)

    req = {"jsonrpc": "2.0", "method": "health", "params": {}, "id": "req-2"}
    resp = await async_client.post("/api/mcp-gateway/fast-filesystem/rpc", json=req)
    assert resp.status_code == 502
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-2"
    assert body["error"]["code"] == -32002
