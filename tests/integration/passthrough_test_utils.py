"""Utilitaires partagés pour tester la route /v1/chat/completions."""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI

from kimi_proxy.api.routes import mcp_passthrough
from kimi_proxy.proxy import passthrough as passthrough_module


class FakeProxyClient:
    """Client HTTP factice qui capture le body réellement envoyé."""

    def __init__(self, captured_bodies: list[bytes]):
        self.captured_bodies = captured_bodies

    def build_request(self, method: str, url: str, headers=None, content=None) -> httpx.Request:
        return httpx.Request(method, url, headers=headers, content=content)

    async def send(self, request: httpx.Request, provider_type: str = "openai") -> httpx.Response:
        self.captured_bodies.append(request.content)
        return httpx.Response(200, json={"ok": True}, request=request)

    async def send_streaming(self, request: httpx.Request, provider_type: str = "openai") -> httpx.Response:
        self.captured_bodies.append(request.content)
        return httpx.Response(200, content=b'data: {"ok": true}\n\n', request=request)


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(mcp_passthrough.router)
    return app


def patch_passthrough(monkeypatch, *, config: dict[str, Any], captured: list[bytes]) -> None:
    monkeypatch.setenv("KIMI_ENV", "development")
    monkeypatch.setattr(mcp_passthrough, "get_config", lambda: config)
    monkeypatch.setattr(passthrough_module, "get_config", lambda: config)
    monkeypatch.setattr(
        passthrough_module,
        "create_proxy_client",
        lambda **kwargs: FakeProxyClient(captured),
    )


def target_headers() -> dict[str, str]:
    return {
        "X-Target-Base-URL": "http://localhost:9999/v1",
        "Authorization": "Bearer test-provider-key",
    }
