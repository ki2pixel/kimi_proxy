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


@pytest.mark.asyncio
async def test_gateway_tools_call_prunes_then_masks_in_order(monkeypatch, async_client: httpx.AsyncClient):
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_ENABLED", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MIN_CHARS", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MAX_CHARS_FALLBACK", "0")

    calls: dict[str, object] = {"pruner": 0, "seen_pruner_text": None}

    upstream_text = "O" * 12_000
    pruned_text = "PRUNED_HEAD " + ("P" * 9_000)

    async def _fake_forward_jsonrpc(server_name: str, request_json: object, *, timeout_s: float = 30.0) -> object:
        _ = timeout_s
        if server_name == "pruner":
            calls["pruner"] = int(calls["pruner"]) + 1
            assert isinstance(request_json, dict)
            params = request_json.get("params")
            assert isinstance(params, dict)
            arguments = params.get("arguments")
            assert isinstance(arguments, dict)
            seen_text = arguments.get("text")
            assert isinstance(seen_text, str)
            calls["seen_pruner_text"] = seen_text
            payload = {
                "prune_id": "p1",
                "pruned_text": pruned_text,
                "warnings": [],
                "stats": {"used_fallback": False},
            }
            return {
                "jsonrpc": "2.0",
                "id": 9001,
                "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
            }

        return {
            "jsonrpc": "2.0",
            "id": "req-prune-mask",
            "result": {"content": [{"type": "text", "text": upstream_text}]},
        }

    monkeypatch.setattr(mcp_gateway, "forward_jsonrpc", _fake_forward_jsonrpc)

    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/tmp/x"}},
        "id": "req-prune-mask",
    }
    resp = await async_client.post("/api/mcp-gateway/fast-filesystem/rpc", json=req)
    assert resp.status_code == 200

    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-prune-mask"
    assert calls["pruner"] == 1
    assert isinstance(calls["seen_pruner_text"], str)

    # Preuve d'ordre prune-then-mask:
    # le pruner doit voir le texte upstream brut, non déjà masqué.
    seen_text = str(calls["seen_pruner_text"])
    assert seen_text == upstream_text
    assert "KIMI_PROXY_OBSERVATION_MASKED" not in seen_text

    # Puis la réponse prunée repasse dans le masking gateway.
    final_text = body["result"]["content"][0]["text"]
    assert isinstance(final_text, str)
    assert "PRUNED_HEAD" in final_text
    assert "KIMI_PROXY_OBSERVATION_MASKED" in final_text


@pytest.mark.asyncio
async def test_gateway_tools_call_under_threshold_does_not_call_pruner(monkeypatch, async_client: httpx.AsyncClient):
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_ENABLED", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MIN_CHARS", "5000")

    async def _fake_forward_jsonrpc(server_name: str, request_json: object, *, timeout_s: float = 30.0) -> object:
        _ = request_json
        _ = timeout_s
        if server_name == "pruner":
            raise AssertionError("pruner must not be called under threshold")
        return {
            "jsonrpc": "2.0",
            "id": "req-under-threshold",
            "result": {"content": [{"type": "text", "text": "short"}]},
        }

    monkeypatch.setattr(mcp_gateway, "forward_jsonrpc", _fake_forward_jsonrpc)

    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/tmp/x"}},
        "id": "req-under-threshold",
    }
    resp = await async_client.post("/api/mcp-gateway/fast-filesystem/rpc", json=req)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-under-threshold"
    assert body["result"]["content"][0]["text"] == "short"


@pytest.mark.asyncio
async def test_gateway_tools_call_excluded_path_skips_pruner_but_still_masks(monkeypatch, async_client: httpx.AsyncClient):
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_ENABLED", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MIN_CHARS", "1")

    upstream_text = "O" * 12_000

    async def _fake_forward_jsonrpc(server_name: str, request_json: object, *, timeout_s: float = 30.0) -> object:
        _ = request_json
        _ = timeout_s
        if server_name == "pruner":
            raise AssertionError("pruner must not be called for excluded paths")
        return {
            "jsonrpc": "2.0",
            "id": "req-excluded-path",
            "result": {"content": [{"type": "text", "text": upstream_text}]},
        }

    monkeypatch.setattr(mcp_gateway, "forward_jsonrpc", _fake_forward_jsonrpc)

    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/repo/.clinerules/rules.md"}},
        "id": "req-excluded-path",
    }
    resp = await async_client.post("/api/mcp-gateway/fast-filesystem/rpc", json=req)
    assert resp.status_code == 200

    body = resp.json()
    final_text = body["result"]["content"][0]["text"]
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-excluded-path"
    assert "KIMI_PROXY_OBSERVATION_MASKED" in final_text
    assert final_text.startswith("O" * 2000)


@pytest.mark.asyncio
async def test_gateway_non_tools_call_is_not_pruned(monkeypatch, async_client: httpx.AsyncClient):
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_ENABLED", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MIN_CHARS", "1")

    upstream_response = {
        "jsonrpc": "2.0",
        "id": "req-tools-list",
        "result": {"tools": [{"name": "health"}]},
    }

    async def _fake_forward_jsonrpc(server_name: str, request_json: object, *, timeout_s: float = 30.0) -> object:
        _ = request_json
        _ = timeout_s
        if server_name == "pruner":
            raise AssertionError("pruner must not be called for non tools/call")
        return upstream_response

    monkeypatch.setattr(mcp_gateway, "forward_jsonrpc", _fake_forward_jsonrpc)

    req = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": "req-tools-list"}
    resp = await async_client.post("/api/mcp-gateway/fast-filesystem/rpc", json=req)
    assert resp.status_code == 200
    body = resp.json()
    assert body == upstream_response


@pytest.mark.asyncio
async def test_gateway_pruner_timeout_is_fail_open(monkeypatch, async_client: httpx.AsyncClient):
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_ENABLED", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MIN_CHARS", "1")
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_MAX_CHARS_FALLBACK", "0")

    calls: dict[str, int] = {"pruner": 0}

    async def _fake_forward_jsonrpc(server_name: str, request_json: object, *, timeout_s: float = 30.0) -> object:
        _ = request_json
        _ = timeout_s
        if server_name == "pruner":
            calls["pruner"] += 1
            raise mcp_gateway.MCPGatewayUpstreamError(
                code="timeout",
                message="Timeout",
                details={"source": "test"},
            )
        return {
            "jsonrpc": "2.0",
            "id": "req-fail-open",
            "result": {"content": [{"type": "text", "text": "ORIGINAL_SAFE"}]},
        }

    monkeypatch.setattr(mcp_gateway, "forward_jsonrpc", _fake_forward_jsonrpc)

    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/tmp/x"}},
        "id": "req-fail-open",
    }
    resp = await async_client.post("/api/mcp-gateway/fast-filesystem/rpc", json=req)
    assert resp.status_code == 200

    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "req-fail-open"
    assert calls["pruner"] == 1
    # Fail-open: la réponse reste exploitable et ne casse pas le contrat JSON-RPC.
    assert body["result"]["content"][0]["text"] == "ORIGINAL_SAFE"
