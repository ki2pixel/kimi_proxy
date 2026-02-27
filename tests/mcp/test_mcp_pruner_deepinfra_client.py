import httpx
import pytest

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
        return httpx.Response(200, json={"scores": [0.1, 0.9]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        async with DeepInfraClient(cfg, http_client=http_client) as client:
            result = await client.rerank(query="q", documents=["a", "b"])

    assert result.scores_by_index == {0: 0.1, 1: 0.9}
    assert result.elapsed_ms >= 0


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
