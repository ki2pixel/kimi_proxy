# Proxy Layer - Routage HTTP Intelligent

## TL;DR
Couche proxy orchestrant 8 providers, 20+ modèles avec routage intelligent, transformation formats (Gemini), streaming SSE, et gestion erreurs robuste.

## Problème
La couche proxy gère des opérations HTTP complexes avec haute complexité cyclomatique sans documentation des patterns de routage et gestion erreurs.

## Architecture 5 Couches
Le Proxy Layer est la quatrième couche, gérant le routage HTTP vers les APIs externes tout en dépendant du Core layer.

```
API Layer ← Services Layer ← Features Layer ← Proxy Layer (HTTPX, Transformers) ← Core Layer (SQLite)
```

## Composants Principaux

### Router
**Localisation** : `src/kimi_proxy/proxy/router.py`
**Responsabilités** :
- Routage intelligent provider → modèle
- Mapping noms modèles standardisés
- Gestion capacités contexte
- Optimisation coûts/latence

**Smart Routing Algorithm** :
```python
def select_optimal_provider(model: str, context_size: int) -> ProviderConfig:
    """Sélectionne le provider optimal selon contexte/coût/latence"""
    candidates = get_providers_for_model(model)
    
    # Filtrage par capacité contexte
    viable = [p for p in candidates if p.max_context >= context_size]
    
    # Tri par coût puis latence
    return min(viable, key=lambda p: (p.cost_per_token, p.avg_latency))
```

### Transformers
**Localisation** : `src/kimi_proxy/proxy/transformers.py`
**Responsabilités** :
- Conversion formats entre providers
- Normalisation réponses API
- Gestion spécificités (Gemini, Claude)
- Validation structures

**Exemple Transformation Gemini** :
```python
def transform_gemini_to_openai(gemini_response: dict) -> dict:
    """Convertit format Gemini vers OpenAI standard"""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": gemini_response.get("model", "gemini-pro"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": gemini_response["candidates"][0]["content"]["parts"][0]["text"]
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": gemini_response["usageMetadata"]["promptTokenCount"],
            "completion_tokens": gemini_response["usageMetadata"]["candidatesTokenCount"],
            "total_tokens": gemini_response["usageMetadata"]["totalTokenCount"]
        }
    }
```

### Stream Manager
**Localisation** : `src/kimi_proxy/proxy/stream.py`
**Responsabilités** :
- Gestion streaming Server-Sent Events
- Extraction tokens temps réel
- Gestion erreurs streaming
- Buffering optimisé

**Fonction Critique** : `stream_generator` (Score C - 25)
```python
async def stream_generator(response: httpx.Response):
    """Génère stream SSE avec extraction tokens"""
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        
        # Extraction tokens depuis chunk partiel
        if "data: " in buffer:
            lines = buffer.split("\n")
            for line in lines:
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: "
                    if data != "[DONE]":
                        yield parse_sse_data(data)
```

### HTTP Client
**Localisation** : `src/kimi_proxy/proxy/client.py`
**Responsabilités** :
- Client HTTPX asynchrone configuré
- Gestion timeouts et retries
- Support authentification multiple
- Monitoring performance

## Haute Complexité - Pattern 6

### Fonction `_proxy_to_provider` (Score E - 30-39)
**Localisation** : `src/kimi_proxy/api/routes/proxy.py`
**Complexité** : Orchestration complexe des appels API avec transformation formats, gestion timeouts, et récupération erreurs.

```python
async def _proxy_to_provider(
    request: ChatCompletionRequest,
    provider_config: ProviderConfig
) -> ChatCompletionResponse:
    """Appel HTTP vers provider avec transformation et retry"""
    
    # Transformation format provider-spécifique
    provider_request = transform_to_provider_format(request, provider_config)
    
    # Configuration client HTTPX
    timeout = httpx.Timeout(
        connect=provider_config.connect_timeout,
        read=provider_config.read_timeout,
        write=provider_config.write_timeout
    )
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                provider_config.endpoint,
                headers=provider_config.headers,
                json=provider_request
            )
            response.raise_for_status()
            
            # Transformation vers format standard
            return transform_from_provider_format(response.json(), provider_config)
            
    except httpx.TimeoutException as e:
        # Extraction tokens partiels du timeout
        partial_usage = extract_partial_usage_from_error(e)
        raise ProxyTimeoutError(
            f"Timeout calling {provider_config.name}",
            partial_usage=partial_usage
        )
    except httpx.ConnectError as e:
        # Retry avec backoff exponentiel
        return await retry_with_backoff(request, provider_config, max_retries=3)
```

### Fonction `extract_usage_from_stream` (Score C - 20)
**Localisation** : `src/kimi_proxy/proxy/stream.py`
**Complexité** : Extraction tokens depuis streams partiellement corrompus avec calcul cumulatif.

```python
def extract_usage_from_stream(corrupted_stream: str) -> TokenUsage:
    """Extraction tokens depuis stream corrompu"""
    
    # Pattern matching pour trouver usage tokens
    usage_pattern = r'"usage":\s*{[^}]*}'
    matches = re.findall(usage_pattern, corrupted_stream)
    
    cumulative_usage = TokenUsage(
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0
    )
    
    for match in matches:
        try:
            usage_data = json.loads(match)
            cumulative_usage["prompt_tokens"] += usage_data.get("prompt_tokens", 0)
            cumulative_usage["completion_tokens"] += usage_data.get("completion_tokens", 0)
            cumulative_usage["total_tokens"] += usage_data.get("total_tokens", 0)
        except json.JSONDecodeError:
            # Ignorer les corrompus
            continue
    
    return cumulative_usage
```

## Patterns Système Appliqués

### Pattern 6 - Error Handling Robuste
```python
# ✅ CORRECT - Extraction tokens partiels
try:
    response = await client.post(url, json=data)
    response.raise_for_status()
    return response.json()
except httpx.TimeoutException as e:
    # Récupération tokens même en erreur
    partial_usage = extract_usage_from_timeout(e)
    logger.warning(f"Timeout with partial usage: {partial_usage}")
    raise ProxyTimeoutError("Provider timeout", partial_usage=partial_usage)

# ❌ INCORRECT - Perte d'information
try:
    response = await client.post(url, json=data)
    return response.json()
except Exception:
    return {"error": "Failed"}  # Tokens perdus!
```

### Pattern 15 - Circuit Breaker
```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()
        
        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise
```

## Trade-offs
| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Streaming direct | Latence minimale | Complexité gestion erreurs |
| Buffering complet | Fiabilité maximale | Latence accrue |
| **Choix Kimi Proxy** | **Équilibre avec extraction partielle** | **Complexité maintenue** |

## Golden Rule
**Toute nouvelle fonctionnalité proxy doit :**
1. Inclure transformation formats bidirectionnelle
2. Gérer extraction tokens partiels en erreur
3. Utiliser circuit breaker pour providers
4. Monitorer latence et taux erreur
5. Documenter les invariants de transformation

## Métriques Actuelles
- **8 providers** configurés (OpenAI, Anthropic, Google, etc.)
- **20+ modèles** supportés avec mapping intelligent
- **Complexité moyenne** : C (17.42) - 2 fonctions E/F
- **Taux erreur** : < 1% avec retry automatique
- **Latence moyenne** : 850ms (incluant transformation)

## Prochaines Évolutions
- [ ] Load balancing actif entre providers
- [ ] Cache intelligent des réponses
- [ ] Monitoring temps réel Prometheus
- [ ] Auto-scaling basé sur charge

---
*Dernière mise à jour : 2026-02-20*  
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*