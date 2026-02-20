# Couche Proxy : Routage et Streaming LLM

**TL;DR**: La couche proxy intercepte les requêtes `/chat/completions`, applique les transformations provider-spécifiques, puis stream les réponses via SSE. Complexité F justifiée par gestion erreurs réseau et transformations format.

## Le Problème du Multi-Provider

Vous envoyez une requête OpenAI-format. Le provider cible utilise Gemini-format. Le proxy doit transformer sans casser le streaming.

## ❌ Approche Monolithique (Avant)

```python
# Tout dans une fonction géante
async def proxy_chat(request, provider):
    # 50+ lignes de logique mélangée
    if provider == "openai":
        # transformation
    elif provider == "gemini":
        # autre transformation
    # gestion erreurs
    # streaming
```

## ✅ Architecture Modulaire (Actuel)

```python
# Séparation responsabilités
transformers = {
    "gemini": transform_gemini_request,
    "anthropic": transform_anthropic_request
}

async def proxy_chat(request: ChatRequest) -> StreamingResponse:
    provider = router.select_provider(request)
    transformed = transformers[provider](request)
    return await _proxy_to_provider(transformed, provider)
```

## Gestion Erreurs Streaming (Pattern 6)

**TL;DR**: Les fonctions proxy avec complexité F (>10) implémentent une gestion d'erreurs robuste via retry exponentiel et extraction partielle des tokens.

### Problème Initial
Vous envoyez une requête chat/completions. Le stream s'interrompt avec ReadError. Vous perdez le contexte et les tokens déjà consommés.

### ✅ Solution Implémentée
```python
# Dans proxy.py:_proxy_to_provider
try:
    async for chunk in stream:
        yield chunk
        tokens += extract_tokens(chunk)
except (ReadError, TimeoutException) as e:
    logger.warning(f"Stream interrupted: {e}")
    # Retry avec backoff
    await asyncio.sleep(min(2**attempt, 30))
    # Extraction partielle sauvegardée
    if tokens > 0:
        await save_partial_usage(session_id, tokens)
```

### Comparaison Gestion Erreurs

| Approche | Retry | Extraction Partielle | Complexité |
| -------- | ----- | -------------------- | ---------- |
| Basique  | ❌    | ❌                   | A (faible) |
| Robuste  | ✅    | ✅                   | F (élevée)|

### Règle d'Or : Extraction Avant Retry
Toujours extraire les tokens disponibles avant de retenter, pour éviter la perte de métriques même en cas d'échec.

## Architecture Technique

### Flux de Requête

```
Client → /chat/completions → proxy_chat()
                              ↓
                         Router.select_provider()
                              ↓
                         Transformer[provider]()
                              ↓
                         _proxy_to_provider()
                              ↓
                         HTTPX async request
                              ↓
                         stream_generator()
                              ↓
                         SSE → Client
```

### Transformations Supportées

| Provider | Format Entrée | Format Sortie | Complexité |
| -------- | ------------- | ------------- | ---------- |
| OpenAI | OpenAI | OpenAI | Minimal |
| Gemini | OpenAI | Gemini | Moyenne |
| Anthropic | OpenAI | Claude | Haute |
| Mistral | OpenAI | Mistral | Moyenne |

### Gestion Streaming

```python
async def stream_generator(response):
    """Extrait usage et forward SSE"""
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        # Extraction métriques temps réel
        if "usage" in chunk:
            metrics = extract_usage_from_chunk(chunk)
            await update_dashboard(metrics)
        yield f"data: {chunk}\n\n"
```

## Patterns Système Appliqués

- **Pattern 6** : Gestion erreurs avec retry/fallback
- **Pattern 14** : Transformation format sans perte
- **Pattern 19** : Métriques temps réel streaming

## Points Chauds Complexité

### proxy_chat() - Score F
- **Raison** : Gestion multi-provider + streaming + erreurs
- **Solution** : Séparation en fonctions spécialisées

### _proxy_to_provider() - Score D  
- **Raison** : 311 LOC de logique routing
- **Solution** : Refactor en classes ProviderRouter

## Golden Rule : Transforme Puis Stream, Jamais L'Inverse

La transformation doit précéder le streaming; toute modification en cours de stream casse la cohérence des tokens.