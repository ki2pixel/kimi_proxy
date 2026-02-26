from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

from kimi_proxy.features.mcp_pruner.server import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_tools_list_returns_pruner_tools(async_client: httpx.AsyncClient) -> None:
    req = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
    resp = await async_client.post("/rpc", json=req)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1

    result = body.get("result")
    assert isinstance(result, dict)
    tools = result.get("tools")
    assert isinstance(tools, list)

    names = {t.get("name") for t in tools if isinstance(t, dict)}
    assert names == {"prune_text", "recover_text", "health"}

    prune_tool = next(t for t in tools if isinstance(t, dict) and t.get("name") == "prune_text")
    assert isinstance(prune_tool.get("inputSchema"), dict)
    assert prune_tool["inputSchema"].get("required") == ["text", "goal_hint", "source_type", "options"]


@pytest.mark.asyncio
async def test_tools_call_prune_text_and_recover_text(async_client: httpx.AsyncClient) -> None:
    text = "\n".join(
        [
            "import os",
            "",
            "def keep_me():",
            "    return 1",
            "",
            "# noise",
            "x = 1",
            "y = 2",
            "z = 3",
            "",
            "def target_function():",
            "    raise ValueError('boom')",
        ]
    )

    prune_req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "prune_text",
            "arguments": {
                "text": text,
                "goal_hint": "target_function",
                "source_type": "code",
                "options": {
                    "max_prune_ratio": 0.8,
                    "min_keep_lines": 2,
                    "timeout_ms": 1500,
                    "annotate_lines": True,
                    "include_markers": True,
                },
            },
        },
        "id": "p1",
    }

    resp = await async_client.post("/rpc", json=prune_req)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "p1"

    result = body.get("result")
    assert isinstance(result, dict)
    content = result.get("content")
    assert isinstance(content, list)
    assert isinstance(content[0], dict)
    payload = json.loads(str(content[0].get("text")))
    assert isinstance(payload, dict)
    prune_id = payload.get("prune_id")
    assert isinstance(prune_id, str)
    assert prune_id.startswith("prn_")
    assert isinstance(payload.get("pruned_text"), str)
    assert isinstance(payload.get("annotations"), list)
    stats = payload.get("stats")
    assert isinstance(stats, dict)
    assert isinstance(stats.get("tokens_est_before"), int)
    assert isinstance(stats.get("tokens_est_after"), int)

    recover_req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "recover_text",
            "arguments": {
                "prune_id": prune_id,
                "ranges": [{"start_line": 1, "end_line": 3}],
                "include_line_numbers": True,
            },
        },
        "id": "r1",
    }
    rec = await async_client.post("/rpc", json=recover_req)
    assert rec.status_code == 200
    rec_body = rec.json()
    assert rec_body["jsonrpc"] == "2.0"
    assert rec_body["id"] == "r1"

    rec_result = rec_body.get("result")
    assert isinstance(rec_result, dict)
    rec_content = rec_result.get("content")
    assert isinstance(rec_content, list)
    rec_payload = json.loads(str(rec_content[0].get("text")))
    assert isinstance(rec_payload, dict)
    assert "raw_text" in rec_payload
    assert "metadata" in rec_payload


@pytest.mark.asyncio
async def test_recover_text_unknown_prune_id_returns_domain_error(async_client: httpx.AsyncClient) -> None:
    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "recover_text",
            "arguments": {
                "prune_id": "prn_does_not_exist",
                "ranges": [{"start_line": 1, "end_line": 2}],
                "include_line_numbers": False,
            },
        },
        "id": "x1",
    }
    resp = await async_client.post("/rpc", json=req)
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == "x1"
    err = body.get("error")
    assert isinstance(err, dict)
    assert err.get("code") == -32004


@pytest.mark.asyncio
async def test_recover_text_invalid_range_returns_domain_error(async_client: httpx.AsyncClient) -> None:
    # Create a prune_id first
    prune_req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "prune_text",
            "arguments": {
                "text": "a\n" * 5,
                "goal_hint": "a",
                "source_type": "docs",
                "options": {
                    "max_prune_ratio": 0.8,
                    "min_keep_lines": 1,
                    "timeout_ms": 1500,
                    "annotate_lines": False,
                    "include_markers": False,
                },
            },
        },
        "id": "p2",
    }
    resp = await async_client.post("/rpc", json=prune_req)
    body = resp.json()
    payload = json.loads(str(body["result"]["content"][0]["text"]))
    prune_id = str(payload["prune_id"])

    req = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "recover_text",
            "arguments": {
                "prune_id": prune_id,
                "ranges": [{"start_line": 3, "end_line": 2}],
                "include_line_numbers": False,
            },
        },
        "id": "bad-range",
    }
    rec = await async_client.post("/rpc", json=req)
    assert rec.status_code == 200
    rec_body = rec.json()
    err = rec_body.get("error")
    assert isinstance(err, dict)
    assert err.get("code") == -32005
