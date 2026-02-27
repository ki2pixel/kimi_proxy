"""Tests d’intégration — Context Pruning (Lot C2) sur /chat/completions.

Objectif:
- Feature flag OFF => comportement identique (no-op).
- Feature flag ON => le proxy tente de pruner les messages role="tool" via MCP pruner.
- Timeout/erreur upstream => fallback no-op.

Stratégie:
- App FastAPI minimale incluant uniquement `kimi_proxy.api.routes.proxy.router`.
- Patch `_proxy_to_provider` pour capturer le body réellement envoyé, sans réseau.
- Patch `forward_jsonrpc` (proxy.context_pruning) pour simuler:
  - une réponse MCP `tools/call` valide avec markers;
  - une erreur (timeout) pour vérifier le fallback.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

import kimi_proxy.api.routes.proxy as proxy_routes


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
async def test_context_pruning_disabled_keeps_messages_unchanged(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    tool_content = "A" * 5000
    body = _make_body_with_tool_result(tool_content=tool_content)

    config: dict[str, object] = {
        "providers": {"managed:kimi-code": {"type": "openai", "base_url": "http://unused", "api_key": ""}},
        "models": {"nvidia/kimi-k2.5": {"provider": "nvidia", "model": "moonshotai/kimi-k2.5", "max_context_size": 262144}},
        "context_pruning": {"enabled": False},
    }
    _patch_proxy_for_test(monkeypatch, config=config, captured_bodies=captured)

    resp = await async_client.post("/chat/completions", json=body)
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    assert sent["messages"] == body["messages"]


@pytest.mark.asyncio
async def test_context_pruning_enabled_prunes_tool_message(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    tool_content = "A" * 5000
    body = _make_body_with_tool_result(tool_content=tool_content)

    config: dict[str, object] = {
        "providers": {"managed:kimi-code": {"type": "openai", "base_url": "http://unused", "api_key": ""}},
        "models": {"nvidia/kimi-k2.5": {"provider": "nvidia", "model": "moonshotai/kimi-k2.5", "max_context_size": 262144}},
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
    _patch_proxy_for_test(monkeypatch, config=config, captured_bodies=captured)

    # Patch `forward_jsonrpc` pour retourner une réponse MCP `tools/call` plausible.
    import kimi_proxy.proxy.context_pruning as pruning

    async def _fake_forward_jsonrpc(_server_name: str, _request_json: object, *, timeout_s: float = 30.0) -> object:
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
                # On envoie volontairement des champs additionnels pour valider la compat
                # avec les réponses enrichies du serveur (DeepInfra + métriques).
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
            "result": {"content": [{"type": "text", "text": json.dumps(tool_payload, ensure_ascii=False)}]},
        }

    monkeypatch.setattr(pruning, "forward_jsonrpc", _fake_forward_jsonrpc)

    resp = await async_client.post("/chat/completions", json=body)
    assert resp.status_code == 200

    assert len(captured) == 1
    sent = json.loads(captured[0].decode("utf-8"))
    messages = sent["messages"]

    assert len(messages) == len(body["messages"])  # invariant length
    assert messages[2]["role"] == "tool"
    assert isinstance(messages[2]["content"], str)
    assert "⟦PRUNÉ:" in messages[2]["content"]
    assert messages[2].get("_pruner") is not None


@pytest.mark.asyncio
async def test_context_pruning_timeout_falls_back_noop(monkeypatch, async_client: httpx.AsyncClient):
    captured: list[bytes] = []
    tool_content = "A" * 5000
    body = _make_body_with_tool_result(tool_content=tool_content)

    config: dict[str, object] = {
        "providers": {"managed:kimi-code": {"type": "openai", "base_url": "http://unused", "api_key": ""}},
        "models": {"nvidia/kimi-k2.5": {"provider": "nvidia", "model": "moonshotai/kimi-k2.5", "max_context_size": 262144}},
        "context_pruning": {"enabled": True, "min_chars_to_prune": 10, "call_timeout_ms": 1, "options": {}},
    }
    _patch_proxy_for_test(monkeypatch, config=config, captured_bodies=captured)

    import kimi_proxy.proxy.context_pruning as pruning

    async def _boom(*_a, **_kw):
        raise httpx.TimeoutException("Timeout")

    monkeypatch.setattr(pruning, "forward_jsonrpc", _boom)

    resp = await async_client.post("/chat/completions", json=body)
    assert resp.status_code == 200

    sent = json.loads(captured[0].decode("utf-8"))
    assert sent["messages"] == body["messages"]
