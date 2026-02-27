from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

import kimi_proxy.features.mcp_pruner.server as pruner_server


# Garder une référence au vrai AsyncClient avant tout monkeypatch.
# Important: nos tests patchent `pruner_server.httpx.AsyncClient` (module singleton),
# ce qui impacterait aussi le client ASGI du test si on n'utilise pas ce handle.
REAL_HTTPX_ASYNC_CLIENT = httpx.AsyncClient


def _make_prune_req(*, text: str) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "prune_text",
            "arguments": {
                "text": text,
                "goal_hint": "keep",
                "source_type": "docs",
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


def _extract_tool_payload(resp_json: dict[str, object]) -> dict[str, object]:
    result = resp_json.get("result")
    assert isinstance(result, dict)
    content = result.get("content")
    assert isinstance(content, list)
    assert content and isinstance(content[0], dict)
    text = content[0].get("text")
    assert isinstance(text, str)
    payload = json.loads(text)
    assert isinstance(payload, dict)
    return payload


def _make_test_text(*, n_lines: int = 80) -> str:
    # > 60 lignes pour éviter que la baseline heuristique garde tout (head+tail).
    return "\n".join([f"L{i}" for i in range(1, n_lines + 1)])


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIMI_PRUNING_BACKEND", "deepinfra")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    monkeypatch.setenv("DEEPINFRA_ENDPOINT_URL", "https://deepinfra.test/v1/inference")
    monkeypatch.setenv("DEEPINFRA_MAX_DOCS", "256")

    # Évite de lire config.toml (non pertinent pour ces tests).
    monkeypatch.setattr(pruner_server, "get_config", lambda: {})


async def _make_client_for_app(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with REAL_HTTPX_ASYNC_CLIENT(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_success_via_httpx_mocktransport(monkeypatch: pytest.MonkeyPatch, base_env: None) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        body = json.loads(request.content.decode("utf-8"))
        docs = body.get("input", {}).get("documents", []) if isinstance(body, dict) else []
        n = len(docs) if isinstance(docs, list) else 0
        # Scores simples: plus haut au début/fin.
        scores = [0.0] * n
        if n:
            scores[0] = 10.0
            scores[n - 1] = 9.0
        return httpx.Response(200, json={"scores": scores})

    def _fake_async_client(*args, **kwargs) -> httpx.AsyncClient:
        return REAL_HTTPX_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(pruner_server.httpx, "AsyncClient", _fake_async_client)

    app = pruner_server.create_app()
    async for client in _make_client_for_app(app):
        resp = await client.post("/rpc", json=_make_prune_req(text=_make_test_text(n_lines=50)))
        assert resp.status_code == 200
        payload = _extract_tool_payload(resp.json())

    stats = payload.get("stats")
    assert isinstance(stats, dict)
    assert stats.get("backend") == "deepinfra"
    assert stats.get("used_fallback") is False
    assert isinstance(stats.get("deepinfra_latency_ms"), int)

    pruned_text = str(payload.get("pruned_text"))
    assert "⟦PRUNÉ:" in pruned_text

    # Règle critique: si annotate_lines=true, les markers ne doivent JAMAIS être préfixés par "N│".
    for line in pruned_text.splitlines():
        assert "│ ⟦PRUNÉ:" not in line

    assert calls["count"] == 1


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    "mode, expected_warning, expected_status",
    [
        ("timeout", "deepinfra_http_error", None),
        ("401", "deepinfra_http_error", 401),
        ("429", "deepinfra_http_error", 429),
        ("invalid_json", "deepinfra_parse_error", None),
    ],
)
async def test_deepinfra_errors_fallback_to_heuristic(
    monkeypatch: pytest.MonkeyPatch,
    base_env: None,
    mode: str,
    expected_warning: str,
    expected_status: int | None,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        if mode == "timeout":
            raise httpx.TimeoutException("Timeout")
        if mode == "401":
            return httpx.Response(401, json={"error": "unauthorized"})
        if mode == "429":
            return httpx.Response(429, json={"error": "rate_limited"})
        if mode == "invalid_json":
            return httpx.Response(200, content=b"not-json", headers={"content-type": "text/plain"})
        raise AssertionError("Unknown mode")

    def _fake_async_client(*args, **kwargs) -> httpx.AsyncClient:
        return REAL_HTTPX_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(pruner_server.httpx, "AsyncClient", _fake_async_client)

    app = pruner_server.create_app()
    async for client in _make_client_for_app(app):
        resp = await client.post("/rpc", json=_make_prune_req(text=_make_test_text(n_lines=120)))
        assert resp.status_code == 200
        payload = _extract_tool_payload(resp.json())

    stats = payload.get("stats")
    assert isinstance(stats, dict)
    assert stats.get("backend") == "deepinfra"
    assert stats.get("used_fallback") is True
    if expected_status is not None:
        assert stats.get("deepinfra_http_status") == expected_status
    else:
        assert "deepinfra_http_status" not in stats

    warnings = payload.get("warnings")
    assert isinstance(warnings, list)
    assert "deepinfra_error" in warnings
    assert expected_warning in warnings


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_cache_hits_avoid_second_http_call(monkeypatch: pytest.MonkeyPatch, base_env: None) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        body = json.loads(request.content.decode("utf-8"))
        docs = body.get("input", {}).get("documents", []) if isinstance(body, dict) else []
        n = len(docs) if isinstance(docs, list) else 0
        return httpx.Response(200, json={"scores": [1.0] * n})

    def _fake_async_client(*args, **kwargs) -> httpx.AsyncClient:
        return REAL_HTTPX_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(pruner_server.httpx, "AsyncClient", _fake_async_client)

    app = pruner_server.create_app()
    async for client in _make_client_for_app(app):
        req = _make_prune_req(text=_make_test_text(n_lines=50))

        r1 = await client.post("/rpc", json=req)
        assert r1.status_code == 200
        p1 = _extract_tool_payload(r1.json())
        assert calls["count"] == 1

        r2 = await client.post("/rpc", json=req)
        assert r2.status_code == 200
        p2 = _extract_tool_payload(r2.json())
        assert calls["count"] == 1

    stats2 = p2.get("stats")
    assert isinstance(stats2, dict)
    assert stats2.get("deepinfra_cached") is True
    assert stats2.get("deepinfra_latency_ms") == 0

    warnings2 = p2.get("warnings")
    assert isinstance(warnings2, list)
    assert "cache_hit" in warnings2

    # prune_id diffère (remplacement <pending>), même si pruned_text est issu du cache
    assert p1.get("prune_id") != p2.get("prune_id")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_health_endpoint_and_tool_health_include_metrics(monkeypatch: pytest.MonkeyPatch, base_env: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        docs = body.get("input", {}).get("documents", []) if isinstance(body, dict) else []
        n = len(docs) if isinstance(docs, list) else 0
        return httpx.Response(200, json={"scores": [1.0] * n})

    def _fake_async_client(*args, **kwargs) -> httpx.AsyncClient:
        return REAL_HTTPX_ASYNC_CLIENT(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(pruner_server.httpx, "AsyncClient", _fake_async_client)

    app = pruner_server.create_app()
    async for client in _make_client_for_app(app):
        # One prune call to increment metrics
        resp = await client.post("/rpc", json=_make_prune_req(text=_make_test_text(n_lines=30)))
        assert resp.status_code == 200

        health_http = await client.get("/health")
        assert health_http.status_code == 200
        health_payload = health_http.json()
        assert isinstance(health_payload, dict)
        assert isinstance(health_payload.get("metrics"), dict)

        tool_req = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "health", "arguments": {}}, "id": "h"}
        tool_resp = await client.post("/rpc", json=tool_req)
        assert tool_resp.status_code == 200
        tool_payload = _extract_tool_payload(tool_resp.json())
        assert isinstance(tool_payload.get("metrics"), dict)
