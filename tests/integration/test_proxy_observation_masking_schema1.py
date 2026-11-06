"""Tests d'intégration — Observation Masking Schéma 1 sur /v1/chat/completions."""
from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest

from .passthrough_test_utils import make_app, patch_passthrough, target_headers


def _make_tool_heavy_body() -> dict[str, object]:
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
            {"role": "tool", "tool_call_id": "call_1", "content": "A" * 1000},
            {"role": "user", "content": "next"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "fast_read_file", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_2", "content": "OK"},
            {"role": "user", "content": "done"},
        ],
    }


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_schema1_disabled_keeps_messages_unchanged(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_tool_heavy_body()
    config = {
        "observation_masking": {"schema1": {"enabled": False}},
    }
    patch_passthrough(monkeypatch=monkeypatch, config=config, captured=captured)

    resp = await async_client.post("/v1/chat/completions", json=body, headers=target_headers())
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    assert sent["messages"] == body["messages"]


@pytest.mark.asyncio
async def test_schema1_enabled_masks_old_tool_results(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_tool_heavy_body()
    config = {
        "observation_masking": {
            "schema1": {
                "enabled": True,
                "window_turns": 1,
                "keep_errors": True,
                "keep_last_k_per_tool": 0,
            }
        },
    }
    patch_passthrough(monkeypatch=monkeypatch, config=config, captured=captured)

    resp = await async_client.post("/v1/chat/completions", json=body, headers=target_headers())
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    messages = sent["messages"]

    assert len(messages) == len(body["messages"])
    assert messages[2]["tool_call_id"] == "call_1"
    assert isinstance(messages[2]["content"], str)
    assert "Observation masquée" in messages[2]["content"]
    assert "call_1" in messages[2]["content"]
    assert "fast_read_file" in messages[2]["content"]
    assert messages[5]["content"] == "OK"


@pytest.mark.asyncio
async def test_proxy_normalizes_tool_call_arguments_before_upstream(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = {
        "model": "nvidia/kimi-k2.5",
        "stream": False,
        "messages": [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "bad-id",
                        "type": "function",
                        "function": {
                            "name": "fast_read_file",
                            "arguments": '{"query":"abc" "limit":3}',
                        },
                    }
                ],
            },
            {"role": "user", "content": "continue"},
        ],
    }
    config = {"observation_masking": {"schema1": {"enabled": False}}}
    patch_passthrough(monkeypatch=monkeypatch, config=config, captured=captured)

    resp = await async_client.post("/v1/chat/completions", json=body, headers=target_headers())
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    tool_call = sent["messages"][0]["tool_calls"][0]
    assert tool_call["id"] == "bad-id"
    assert json.loads(tool_call["function"]["arguments"]) == {"query": "abc", "limit": 3}
