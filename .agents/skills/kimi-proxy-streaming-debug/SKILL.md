---
name: kimi-proxy-streaming-debug
description: Expert debugging for SSE streaming in Kimi Proxy Middleware MCP. Use when encountering ReadError, TimeoutException, ConnectError, truncated streams, or client disconnects.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Streaming Debug

**TL;DR**: `proxy/stream.py` est un relay SSE pur. Il ne bufferise pas, n'extrait pas de tokens et n'avale pas les erreurs. Les erreurs réseau remontent à FastAPI ; les retries se font au niveau requête dans `proxy/client.py`.

## Source of Truth

- `src/kimi_proxy/proxy/stream.py`
- `src/kimi_proxy/proxy/client.py`
- `src/kimi_proxy/proxy/passthrough.py`
- `src/kimi_proxy/api/routes/mcp_passthrough.py`
- `tests/unit/proxy/test_stream.py`
- `tests/e2e/test_streaming_errors.py`

## Comportement actuel

```python
async def stream_generator(response: httpx.Response):
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    finally:
        await response.aclose()
        client = getattr(response, "_client_ref", None)
        if client is not None:
            await client.aclose()
```

- Aucun buffer de 256 Ko.
- Aucune extraction `usage`.
- Aucun `STREAMING_ERROR_TYPES`.
- Aucun broadcast WebSocket.
- Fermeture explicite de la réponse et du client HTTPX.

## Erreurs

| Erreur | Où | Effet |
| :--- | :--- | :--- |
| `httpx.ReadError` | `client.send` / `send_streaming` | Retry réseau si tentatives restantes |
| `httpx.ConnectError` | `client.send` / `send_streaming` | Retry réseau |
| `httpx.TimeoutException` | `client.send` / `send_streaming` | Retry réseau, puis 504 |
| Erreur pendant le flux | `stream_generator` | Remonte à FastAPI ; pas de reprise |

Les réponses 4xx/5xx ne sont pas retryées ; `passthrough.forward` les convertit en `JSONResponse`.

## Timeouts

- `PROVIDER_TIMEOUTS` dans `proxy/client.py` définit les timeouts par provider.
- Aucun timeout par chunk dans `stream.py`.
- Le client HTTPX est créé avec `timeout=120.0` et `max_retries=2` dans le passthrough.

## Debug

```bash
./bin/kimi-proxy logs | tail -100
PYTHONPATH=src venv/bin/python -m pytest tests/unit/proxy/test_stream.py -q
PYTHONPATH=src venv/bin/python -m pytest tests/e2e/test_streaming_errors.py -q
```

Vérifier :

1. Le provider répond-il en SSE (`data: ...`) et non en JSON bufferisé ?
2. Le header `Accept` est-il correct ?
3. Le client ASGI consomme-t-il le flux jusqu'au bout ?
4. Le `X-Target-Base-URL` inclut-il le bon suffixe (`/v1`) ?
5. Le client HTTPX est-il fermé (`_client_ref`) ?

## ❌ Ne pas documenter

- Reprise de stream avec replay de chunks.
- Extraction de tokens partiels après erreur.
- Broadcast WebSocket d'erreur.
- `StreamingError` : la classe a été supprimée.

## Golden Rule

**Un relay SSE ne guérit pas un flux cassé ; il le termine proprement.** Si vous voulez de la reprise, ajoutez-la explicitement avec un protocole et des tests, pas comme comportement implicite.
