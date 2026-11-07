"""Relay SSE pur entre le provider et le client."""
from typing import AsyncGenerator

import httpx


async def close_stream_resources(response: httpx.Response) -> None:
    """Ferme la réponse et le client HTTPX associé au flux."""
    await response.aclose()
    client = getattr(response, "_client_ref", None)
    if client is not None:
        await client.aclose()


async def stream_generator(response: httpx.Response) -> AsyncGenerator[bytes, None]:
    """Relaye les octets du provider et libère les ressources en fin de flux."""
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await close_stream_resources(response)
