from __future__ import annotations

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


def _patch_proxy_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        proxy_routes,
        "get_config",
        lambda: {
            "providers": {
                "nvidia": {
                    "type": "openai",
                    "base_url": "https://integrate.api.nvidia.com/v1",
                    "api_key": "nvapi-test",
                }
            },
            "models": {
                "nvidia/kimi-k2-thinking": {
                    "provider": "nvidia",
                    "model": "moonshotai/kimi-k2-thinking",
                    "max_context_size": 262144,
                }
            },
        },
    )
    monkeypatch.setattr(
        proxy_routes,
        "get_active_session",
        lambda: {"id": 496, "provider": "nvidia", "model": "nvidia/kimi-k2-thinking"},
    )
    monkeypatch.setattr(proxy_routes, "save_metric", lambda **_kwargs: 1)
    monkeypatch.setattr(proxy_routes, "get_session_cumulative_tokens", lambda _session_id: {"total_tokens": 0})
    monkeypatch.setattr(proxy_routes, "get_target_url_for_session", lambda *_a, **_kw: "https://integrate.api.nvidia.com/v1")
    monkeypatch.setattr(proxy_routes, "get_max_context_for_session", lambda *_a, **_kw: 262144)

    class _AutoTrigger:
        async def check_and_trigger(self, **_kwargs):
            return None

    monkeypatch.setattr("kimi_proxy.features.compaction.auto_trigger.get_auto_trigger", lambda: _AutoTrigger())

    class _Limiter:
        async def throttle_if_needed(self):
            return {
                "allowed": True,
                "current_rpm": 1,
                "max_rpm": 40,
                "percentage": 2.5,
                "throttled": False,
                "wait_time": 0,
            }

    monkeypatch.setattr(proxy_routes, "get_rate_limiter", lambda: _Limiter())

    import kimi_proxy.core.auto_session as auto_session

    monkeypatch.setattr(auto_session, "process_auto_session", lambda _json, current: (current, False))


@pytest.mark.asyncio
async def test_proxy_returns_structured_429_when_nvidia_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
    async_client: httpx.AsyncClient,
) -> None:
    _patch_proxy_dependencies(monkeypatch)

    class _ProxyClient:
        async def send_streaming(self, _request: httpx.Request, provider_type: str = "openai") -> httpx.Response:
            assert provider_type == "openai"
            return httpx.Response(
                429,
                text='{"status":429,"title":"Too Many Requests"}',
                headers={"retry-after": "3"},
                request=httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions"),
            )

    monkeypatch.setattr("kimi_proxy.proxy.client.create_proxy_client", lambda **_kwargs: _ProxyClient())

    response = await async_client.post(
        "/chat/completions",
        json={
            "model": "nvidia/kimi-k2-thinking",
            "stream": True,
            "messages": [{"role": "user", "content": "test"}],
        },
    )

    assert response.status_code == 429
    assert response.headers.get("retry-after") == "3"
    body = response.json()
    assert body["error"] == "Provider rate limit exceeded"
    assert body["provider"] == "nvidia"
    assert body["retry_after"] == "3"