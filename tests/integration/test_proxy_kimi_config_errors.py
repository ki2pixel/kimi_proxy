from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI

import kimi_proxy.api.routes.proxy as proxy_routes


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


def _patch_proxy_dependencies(monkeypatch, *, config: dict[str, object]) -> None:
    monkeypatch.setattr(proxy_routes, "get_config", lambda: config)
    monkeypatch.setattr(
        proxy_routes,
        "get_active_session",
        lambda: {"id": 1, "provider": "managed:kimi-code", "model": "kimi-code/kimi-for-coding"},
    )

    monkeypatch.setattr(proxy_routes, "save_metric", lambda **_kwargs: 1)
    monkeypatch.setattr(proxy_routes, "get_session_cumulative_tokens", lambda _session_id: {"total_tokens": 0})

    class _AutoTrigger:
        async def check_and_trigger(self, **_kwargs):
            return None

    monkeypatch.setattr("kimi_proxy.features.compaction.auto_trigger.get_auto_trigger", lambda: _AutoTrigger())
    monkeypatch.setattr(proxy_routes, "get_target_url_for_session", lambda *_a, **_kw: "https://api.kimi.com/coding/v1")
    monkeypatch.setattr(proxy_routes, "get_max_context_for_session", lambda *_a, **_kw: 262144)

    import kimi_proxy.core.auto_session as auto_session

    monkeypatch.setattr(
        auto_session,
        "process_auto_session",
        lambda _json, current: (current, False),
    )


@pytest.mark.asyncio
async def test_proxy_returns_503_when_kimi_provider_missing(monkeypatch, async_client: httpx.AsyncClient) -> None:
    _patch_proxy_dependencies(
        monkeypatch,
        config={
            "providers": {},
            "models": {"kimi-code/kimi-for-coding": {"provider": "managed:kimi-code", "model": "kimi-for-coding"}},
        },
    )

    response = await async_client.post(
        "/chat/completions",
        json={"model": "kimi-code/kimi-for-coding", "stream": False, "messages": [{"role": "user", "content": "test"}]},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "Provider configuration missing"
    assert body["provider"] == "managed:kimi-code"


@pytest.mark.asyncio
async def test_proxy_returns_503_when_kimi_api_key_missing(monkeypatch, async_client: httpx.AsyncClient) -> None:
    _patch_proxy_dependencies(
        monkeypatch,
        config={
            "providers": {
                "managed:kimi-code": {
                    "type": "kimi",
                    "base_url": "https://api.kimi.com/coding/v1",
                    "api_key": "",
                }
            },
            "models": {"kimi-code/kimi-for-coding": {"provider": "managed:kimi-code", "model": "kimi-for-coding"}},
        },
    )

    response = await async_client.post(
        "/chat/completions",
        json={"model": "kimi-code/kimi-for-coding", "stream": False, "messages": [{"role": "user", "content": "test"}]},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "Provider API key missing"
    assert body["provider"] == "managed:kimi-code"