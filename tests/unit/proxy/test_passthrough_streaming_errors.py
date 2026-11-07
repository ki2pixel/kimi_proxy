"""Tests de libération des ressources HTTPX sur erreur streaming."""
from __future__ import annotations

import httpx
import pytest

import kimi_proxy.proxy.passthrough as passthrough_module
from kimi_proxy.proxy.passthrough import PassthroughProcessor


class _FakeAsyncClient:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 429
        self.headers: dict[str, str] = {}
        self.closed = False

    async def aread(self) -> bytes:
        return b'{"error": "quota exceeded"}'

    async def aclose(self) -> None:
        self.closed = True


class _FakeProxyClient:
    def __init__(self, response: _FakeResponse, http_client_ref: _FakeAsyncClient) -> None:
        self.response = response
        self.http_client_ref = http_client_ref

    def build_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        content: str | None = None,
    ) -> httpx.Request:
        return httpx.Request(method, url, headers=headers, content=content)

    async def send_streaming(self, request: httpx.Request, provider_type: str = "openai") -> _FakeResponse:
        _ = request
        _ = provider_type
        setattr(self.response, "_client_ref", self.http_client_ref)
        return self.response

    async def send(self, request: httpx.Request, provider_type: str = "openai") -> _FakeResponse:
        raise AssertionError("send() ne doit pas être appelé en mode streaming")


class _FakeRequest:
    def __init__(self) -> None:
        self.headers = {
            "x-target-base-url": "https://api.openai.com/v1",
            "authorization": "Bearer test-key",
        }


@pytest.mark.asyncio
async def test_streaming_error_closes_response_and_client_ref(monkeypatch):
    response = _FakeResponse()
    http_client_ref = _FakeAsyncClient()
    fake_proxy_client = _FakeProxyClient(response, http_client_ref)

    async def _fake_validate(url: str) -> str:
        return url

    monkeypatch.setattr(
        passthrough_module,
        "validate_and_normalize_target_url",
        _fake_validate,
    )
    monkeypatch.setattr(
        passthrough_module,
        "create_proxy_client",
        lambda **kwargs: fake_proxy_client,
    )

    processor = PassthroughProcessor({})
    result = await processor.forward({"stream": True}, {}, _FakeRequest())

    assert result.status_code == 429
    assert response.closed is True
    assert http_client_ref.closed is True
