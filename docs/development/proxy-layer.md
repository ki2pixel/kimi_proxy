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

## Gestion Erreurs Réseau Robuste

| Pattern | Complexité | Justification |
| ------- | ---------- | ------------- |
| Retry exponentiel | +2 | Connexions instables |
| Timeout adaptatif | +3 | Providers variables |
| Extraction partielle | +5 | Tokens déjà reçus |

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