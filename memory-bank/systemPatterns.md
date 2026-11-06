# Patterns Système Récurrents

## Architecture

### Pattern 1 : Architecture 5 Couches

```text
API (FastAPI) ← Services (SSE/callbacks) ← Features (MCP/contexte) ← Proxy (HTTPX) ← Core (SQLite/Tiktoken)
```

Chaque couche ne dépend que des couches inférieures. Core n'a aucune dépendance externe.

### Pattern 2 : Factory Functions & Injection

```python
@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
```

## Code

### Pattern 3 : Async/Await Obligatoire

```python
# ✅ BON
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ INTERDIT
import requests
def fetch_data(url: str) -> dict:
    return requests.get(url).json()
```

La résolution DNS du passthrough utilise `loop.getaddrinfo`, pas `socket.getaddrinfo`.

### Pattern 4 : Typage Strict

```python
from typing import TypedDict

class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

### Pattern 5 : Imports Anti-Circulaires

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.core.models import MCPMemoryEntry
```

## Erreurs et streaming

### Pattern 6 : Gestion d'Erreurs Robuste

```python
try:
    await process_data()
except httpx.ReadError as e:
    logger.error("Flux interrompu: %s", e)
    raise
```

Pas de `except Exception: pass`.

### Pattern 7 : Relay SSE Pur

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

Aucun buffer, aucun broadcast, aucune extraction de tokens.

## Configuration

### Pattern 8 : Configuration Centralisée

```python
from kimi_proxy.config.loader import get_config, get_context_pruning_config

config = get_config()
pruning = get_context_pruning_config(config)
```

Le client fournit la cible et la clé provider ; `config.toml` ne contient ni provider ni modèle.

### Pattern 9 : Secrets en Environnement

```toml
[mcp.qdrant]
api_key = "${QDRANT_API_KEY}"
```

Les secrets ne sont jamais hardcodés dans le code ni dans les logs.

## Tests

### Pattern 10 : Base en Mémoire

```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_database()
```

### Pattern 11 : Mock Patching

```python
def test_mcp_timeout(mocker):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.side_effect = httpx.TimeoutException("Timeout")
    with pytest.raises(MCPConnectionError):
        await client.call("compress", {"text": "test"})
```

## Mémoire MCP

### Pattern 12 : Types de Mémoire

```python
FREQUENT = "frequent"
EPISODIC = "episodic"
SEMANTIC = "semantic"
```

La promotion en `frequent` se fait via `access_count >= FREQUENT_ACCESS_THRESHOLD`. Les entrées sont stockées dans `mcp_memory_entries` ; Qdrant reçoit les vecteurs sémantiques.

### Pattern 13 : Accès SQLite

```python
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM mcp_memory_entries WHERE session_id = ?",
        (session_id,),
    )
```

Jamais de connexion globale ni de concaténation SQL.

## Documentation

### Pattern 14 : Entrées Horodatées

```markdown
[YYYY-MM-DD HH:MM:SS] - Résumé concis
```
