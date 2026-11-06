"""Tests unitaires du relay SSE."""
import httpx
import pytest

from kimi_proxy.proxy.stream import stream_generator


@pytest.mark.anyio
async def test_stream_yields_all_chunks():
    response = httpx.Response(200, content=b"data: hello\n\n")
    chunks = [chunk async for chunk in stream_generator(response)]
    assert b"".join(chunks) == b"data: hello\n\n"


@pytest.mark.anyio
async def test_stream_closes_response_and_client():
    class FakeClient:
        closed = False

        async def aclose(self):
            self.closed = True

    client = FakeClient()
    response = httpx.Response(200, content=b"data: ok\n\n")
    setattr(response, "_client_ref", client)

    chunks = [chunk async for chunk in stream_generator(response)]

    assert b"".join(chunks) == b"data: ok\n\n"
    assert response.is_closed
    assert client.closed


@pytest.mark.anyio
async def test_stream_propagates_read_error():
    response = httpx.Response(200, content=b"data: ok\n\n")

    async def failing_iter():
        yield b"data: ok\n\n"
        raise httpx.ReadError("Connexion perdue")

    response.aiter_bytes = failing_iter

    chunks = []
    with pytest.raises(httpx.ReadError):
        async for chunk in stream_generator(response):
            chunks.append(chunk)

    assert chunks == [b"data: ok\n\n"]
