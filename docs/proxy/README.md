# Proxy Layer — Passthrough HTTPX et SSE

**TL;DR** : la couche Proxy reçoit une requête OpenAI-compatible, valide la cible fournie par le client, applique les headers provider, envoie la requête via HTTPX et relaie la réponse en JSON ou en SSE.

## Problème

Le middleware ne connaît aucun provider à l'avance. Le client fournit `X-Target-Base-URL` et sa clé dans `Authorization`. La couche Proxy doit donc valider une URL arbitraire contre le SSRF, construire une requête propre et ne jamais fuiter la clé dans les logs.

## Composants

### `passthrough.py`

- `resolve_target` : lit `X-Target-Base-URL`, `X-Provider-Type` et `Authorization`.
- `validate_and_normalize_target_url` : validation SSRF asynchrone (schéma, DNS, IP privées/loopback, allowlist).
- `PassthroughProcessor.apply_features` : tool fixing, observation masking, context pruning.
- `PassthroughProcessor.forward` : construit les headers, envoie la requête, retourne `JSONResponse` ou `StreamingResponse`.

### `client.py`

- `ProxyClient.send` : requête non-streaming avec retry sur erreurs réseau.
- `ProxyClient.send_streaming` : requête streaming ; le client HTTPX reste vivant jusqu'à la fin du flux.
- `PROVIDER_TIMEOUTS` : timeouts par type de provider.

Le retry ne s'applique pas aux réponses 4xx/5xx ; elles sont retournées à l'appelant.

### `stream.py`

Relai SSE pur :

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

Aucune extraction de tokens, aucun broadcast, aucun buffer.

### `transformers.py`

- `build_gemini_endpoint` : construit `generateContent` ou `streamGenerateContent`.
- `convert_to_gemini_format` : conversion minimale des messages OpenAI vers Gemini.

La clé Gemini est envoyée via `x-goog-api-key`, jamais en query string.

### `router.py`

- `get_provider_host_header` : extrait le header `Host` de l'URL cible.
- `map_model_name` : mapping simple des clés de modèles configurées.

### `tool_utils.py`

Réparation des `tool_calls` : IDs manquants, arguments JSON malformés, fusion de JSON concaténés. Le circuit breaker limite les tentatives de réparation par process.

## Invariants

1. `Authorization` porte la clé provider, jamais la clé admin.
2. Toute URL cible passe par la validation SSRF.
3. Le streaming utilise `StreamingResponse` et `aiter_bytes`.
4. Le client HTTPX est fermé à la fin du flux.
5. Aucune route `/chat/completions` legacy.

## Golden Rule

**Le Proxy ne connaît pas les providers ; il connaît une cible validée et un contrat HTTP.** Toute logique de provider spécifique reste dans `transformers.py` et reste minimale.
