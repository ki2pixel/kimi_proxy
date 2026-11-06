"""Tests d'intégration — Context Pruning sur /v1/chat/completions."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest

from .passthrough_test_utils import make_app, patch_passthrough, target_headers


def _make_body_with_tool_result(*, tool_content: str) -> dict[str, object]:
    return {
        "model": "nvidia/kimi-k2.5",
        "stream": False,
        "messages": [
            {"role": "system", "content": "S"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "fast_read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": tool_content},
            {"role": "user", "content": "next"},
        ],
    }


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_context_pruning_disabled_keeps_messages_unchanged(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_body_with_tool_result(tool_content="A" * 5000)
    config = {"context_pruning": {"enabled": False}}
    patch_passthrough(monkeypatch=monkeypatch, config=config, captured=captured)

    resp = await async_client.post("/v1/chat/completions", json=body, headers=target_headers())
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    assert sent["messages"] == body["messages"]


@pytest.mark.asyncio
async def test_context_pruning_enabled_prunes_tool_message(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_body_with_tool_result(tool_content="A" * 5000)
    config = {
        "context_pruning": {
            "enabled": True,
            "min_chars_to_prune": 10,
            "call_timeout_ms": 100,
            "options": {
                "max_prune_ratio": 0.5,
                "min_keep_lines": 1,
                "timeout_ms": 10,
                "annotate_lines": True,
                "include_markers": True,
            },
        },
    }
    patch_passthrough(monkeypatch=monkeypatch, config=config, captured=captured)

    import kimi_proxy.proxy.context_pruning as pruning

    async def _fake_forward_jsonrpc(
        _server_name: str,
        _request_json: object,
        *,
        timeout_s: float = 30.0,
    ) -> object:
        _ = timeout_s
        tool_payload = {
            "prune_id": "prn_test",
            "pruned_text": "1│ kept\n⟦PRUNÉ: prune_id=prn_test lignes 2-10 (9) raison=hors focus⟧",
            "annotations": [
                {
                    "kind": "pruned_block",
                    "original_start_line": 2,
                    "original_end_line": 10,
                    "pruned_line_count": 9,
                    "reason": "hors focus",
                    "marker": "⟦PRUNÉ: prune_id=prn_test lignes 2-10 (9) raison=hors focus⟧",
                }
            ],
            "stats": {
                "backend": "deepinfra",
                "tokens_est_before": 100,
                "tokens_est_after": 10,
                "used_fallback": False,
                "pruned_ratio": 0.9,
                "tokens_saved_est": 90,
                "cost_estimated_usd": 0.0000009,
                "deepinfra_latency_ms": 7,
                "deepinfra_cached": False,
            },
            "warnings": [],
        }
        return {
            "jsonrpc": "2.0",
            "id": 101,
            "result": {
                "content": [
                    {"type": "text", "text": json.dumps(tool_payload, ensure_ascii=False)}
                ]
            },
        }

    monkeypatch.setattr(pruning, "forward_jsonrpc", _fake_forward_jsonrpc)

    resp = await async_client.post("/v1/chat/completions", json=body, headers=target_headers())
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    messages = sent["messages"]

    assert len(messages) == len(body["messages"])
    assert messages[2]["role"] == "tool"
    assert isinstance(messages[2]["content"], str)
    assert "⟦PRUNÉ:" in messages[2]["content"]
    assert messages[2].get("_pruner") is not None


@pytest.mark.asyncio
async def test_context_pruning_timeout_falls_back_noop(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_body_with_tool_result(tool_content="A" * 5000)
    config = {
        "context_pruning": {
            "enabled": True,
            "min_chars_to_prune": 10,
            "call_timeout_ms": 1,
            "options": {},
        },
    }
    patch_passthrough(monkeypatch=monkeypatch, config=config, captured=captured)

    import kimi_proxy.proxy.context_pruning as pruning

    async def _boom(*_a, **_kw):
        raise httpx.TimeoutException("Timeout")

    monkeypatch.setattr(pruning, "forward_jsonrpc", _boom)

    resp = await async_client.post("/v1/chat/completions", json=body, headers=target_headers())
    assert resp.status_code == 200

    sent = json.loads(captured[0].decode("utf-8"))
    assert sent["messages"] == body["messages"]
