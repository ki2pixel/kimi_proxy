import logging

import httpx
import pytest

from kimi_proxy.features.mcp_pruner import deepinfra_client as deepinfra_client_module
from kimi_proxy.features.mcp_pruner.deepinfra_client import (
    DeepInfraClient,
    DeepInfraClientConfig,
    DeepInfraHTTPError,
    DeepInfraParseError,
)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_client_rerank_parses_scores_list(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")

    cfg = DeepInfraClientConfig.from_env()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = request.json()
        assert isinstance(body, dict)
        assert body.get("query") == "q"
        assert body.get("documents") == ["a", "b"]
        assert "input" not in body
        return httpx.Response(200, json={"scores": [0.1, 0.9]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        async with DeepInfraClient(cfg, http_client=http_client) as client:
            result = await client.rerank(query="q", documents=["a", "b"])

    assert result.scores_by_index == {0: 0.1, 1: 0.9}
    assert result.elapsed_ms >= 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_client_payload_is_doc_strict_top_level(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")

    cfg = DeepInfraClientConfig.from_env()

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.json()
        assert isinstance(body, dict)
        assert set(body.keys()) == {"query", "documents"}
        assert body["query"] == "goal"
        assert body["documents"] == ["d1", "d2", "d3"]
        return httpx.Response(200, json={"scores": [0.3, 0.2, 0.1]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        async with DeepInfraClient(cfg, http_client=http_client) as client:
            result = await client.rerank(query="goal", documents=["d1", "d2", "d3"])

    assert result.scores_by_index == {0: 0.3, 1: 0.2, 2: 0.1}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_client_rerank_raises_http_error_on_non_200(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")
    cfg = DeepInfraClientConfig.from_env()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate_limited"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        async with DeepInfraClient(cfg, http_client=http_client) as client:
            with pytest.raises(DeepInfraHTTPError) as err:
                await client.rerank(query="q", documents=["a"])
    assert "429" in str(err.value)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_client_http_error_omits_preview_by_default(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")
    cfg = DeepInfraClientConfig.from_env()

    previous_level = deepinfra_client_module.LOGGER.level
    deepinfra_client_module.LOGGER.setLevel(logging.WARNING)
    try:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="token=super-secret")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with DeepInfraClient(cfg, http_client=http_client) as client:
                with pytest.raises(DeepInfraHTTPError) as err:
                    await client.rerank(query="q", documents=["a"])
    finally:
        deepinfra_client_module.LOGGER.setLevel(previous_level)

    assert err.value.details.get("status_code") == 429
    assert "endpoint_url" in err.value.details
    assert "response_preview" not in err.value.details


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_client_http_error_preview_is_redacted_in_debug(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")
    cfg = DeepInfraClientConfig.from_env()

    previous_level = deepinfra_client_module.LOGGER.level
    deepinfra_client_module.LOGGER.setLevel(logging.DEBUG)
    try:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                text="Authorization: Bearer sk-test token=raw-token api_key=raw-key\nline2",
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            async with DeepInfraClient(cfg, http_client=http_client) as client:
                with pytest.raises(DeepInfraHTTPError) as err:
                    await client.rerank(query="q", documents=["a"])
    finally:
        deepinfra_client_module.LOGGER.setLevel(previous_level)

    preview_obj = err.value.details.get("response_preview")
    assert isinstance(preview_obj, str)
    assert "[REDACTED]" in preview_obj
    assert "sk-test" not in preview_obj
    assert "raw-token" not in preview_obj
    assert "raw-key" not in preview_obj


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_client_rerank_raises_parse_error(monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test")
    cfg = DeepInfraClientConfig.from_env()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        async with DeepInfraClient(cfg, http_client=http_client) as client:
            with pytest.raises(DeepInfraParseError):
                await client.rerank(query="q", documents=["a"])
