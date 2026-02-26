"""Tests d’intégration — Observation Masking Schéma 1 sur /chat/completions.

Objectif:
- Valider que le proxy applique (ou non) `mask_old_tool_results` sur `messages`
  selon la config TOML (feature flag) avant l’envoi upstream.

Stratégie:
- App FastAPI minimale incluant uniquement `kimi_proxy.api.routes.proxy.router`
- Patch local de `_proxy_to_provider` pour capturer le body réellement envoyé,
  sans faire de réseau.
- Patch local de `get_config` + helpers pour isoler le test.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

import kimi_proxy.api.routes.proxy as proxy_routes


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
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(proxy_routes.router)
    return app


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _patch_proxy_for_test(monkeypatch, *, config: dict[str, object], captured_bodies: list[bytes]) -> None:
    # Config isolée
    monkeypatch.setattr(proxy_routes, "get_config", lambda: config)

    # Évite DB / sessions / auto-session
    monkeypatch.setattr(proxy_routes, "get_active_session", lambda: None)

    import kimi_proxy.core.auto_session as auto_session

    monkeypatch.setattr(auto_session, "process_auto_session", lambda _json, _current: (None, False))

    # Évite le routing/config display
    monkeypatch.setattr(proxy_routes, "get_target_url_for_session", lambda *_a, **_kw: "http://provider.test")
    monkeypatch.setattr(proxy_routes, "get_max_context_for_session", lambda *_a, **_kw: 999999)

    async def _fake_proxy_to_provider(**kwargs) -> JSONResponse:  # type: ignore[override]
        body = kwargs.get("body")
        if isinstance(body, (bytes, bytearray)):
            captured_bodies.append(bytes(body))
        elif isinstance(body, str):
            captured_bodies.append(body.encode("utf-8"))
        else:
            captured_bodies.append(b"")
        return JSONResponse({"ok": True})

    monkeypatch.setattr(proxy_routes, "_proxy_to_provider", _fake_proxy_to_provider)


@pytest.mark.asyncio
async def test_schema1_disabled_keeps_messages_unchanged(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_tool_heavy_body()

    config: dict[str, object] = {
        "providers": {"managed:kimi-code": {"type": "openai", "base_url": "http://unused", "api_key": ""}},
        "models": {"nvidia/kimi-k2.5": {"provider": "nvidia", "model": "moonshotai/kimi-k2.5", "max_context_size": 262144}},
        "observation_masking": {"schema1": {"enabled": False}},
    }
    _patch_proxy_for_test(monkeypatch, config=config, captured_bodies=captured)

    resp = await async_client.post("/chat/completions", json=body)
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    assert sent["messages"] == body["messages"]


@pytest.mark.asyncio
async def test_schema1_enabled_masks_old_tool_results(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    body = _make_tool_heavy_body()

    config: dict[str, object] = {
        "providers": {"managed:kimi-code": {"type": "openai", "base_url": "http://unused", "api_key": ""}},
        "models": {"nvidia/kimi-k2.5": {"provider": "nvidia", "model": "moonshotai/kimi-k2.5", "max_context_size": 262144}},
        "observation_masking": {
            "schema1": {
                "enabled": True,
                "window_turns": 1,
                "keep_errors": True,
                "keep_last_k_per_tool": 0,
            }
        },
    }
    _patch_proxy_for_test(monkeypatch, config=config, captured_bodies=captured)

    resp = await async_client.post("/chat/completions", json=body)
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    messages = sent["messages"]

    assert len(messages) == len(body["messages"])  # invariants length
    assert messages[2]["tool_call_id"] == "call_1"  # id preserved

    # call_1 old => masked
    assert isinstance(messages[2]["content"], str)
    assert "Observation masquée" in messages[2]["content"]
    assert "call_1" in messages[2]["content"]
    assert "fast_read_file" in messages[2]["content"]

    # call_2 in window => kept
    assert messages[5]["content"] == "OK"
