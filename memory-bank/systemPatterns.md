# Patterns Système Récurrents

## Architecture Patterns

### Pattern 1 : Architecture 5 Couches
```python
# Structure obligatoire - dépendances unidirectionnelles
API Layer (FastAPI) ← Services (WebSocket) ← Features (MCP) ← Proxy (HTTPX) ← Core (SQLite)
# Chaque couche ne dépend que de celles en dessous
```

### Pattern 2 : Factory Functions & Dependency Injection
```python
# Core - Factory pattern
@contextmanager
def get_db():
    conn = sqlite3.connect("sessions.db")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# Services - DI pattern
def get_connection_manager() -> ConnectionManager:
    return manager

@router.websocket("/ws")
async def endpoint(manager: ConnectionManager = Depends(get_connection_manager)):
    await manager.connect(websocket)
```

## Code Patterns

### Pattern 3 : Async/Await Obligatoire
```python
# ✅ BON - HTTPX async
import httpx
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ MAUVAIS - Requests synchrone (INTERDIT)
import requests  # FORBIDDEN
def fetch_data(url: str) -> dict:
    response = requests.get(url)  # BLOQUE L'EVENT LOOP
    return response.json()
```

### Pattern 4 : Typing Strict (No Any)
```python
# ✅ BON - TypedDict pour structures
from typing import TypedDict

class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

def count_tokens(text: str) -> int:
    import tiktoken
    return len(tiktoken.encoding_for_model("gpt-4").encode(text))

# ❌ MAUVAIS - Any non typé
def bad_function(data: Any) -> Any:  # FORBIDDEN
    return data
```

### Pattern 5 : Imports Anti-Circulaires
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.api.routes.sessions import SessionResponse
    # Uniquement pour les hints, pas importé à runtime
```

## Error Handling Patterns

### Pattern 6 : Gestion Erreurs Robuste
```python
# ✅ BON - Toujours logger et propager
try:
    await process_data()
except httpx.ReadError as e:
    logger.error(f"Stream error: {e}")
    raise StreamingError(f"Provider disconnected: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise

# ❌ MAUVAIS - Catch vide (BUGS CACHÉS)
try:
    await process_data()
except Exception:
    pass  # JAMAIS!
```

### Pattern 7 : Streaming Error Recovery
```python
async def stream_generator(response, session_id, metric_id, provider_type, models, manager):
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    except httpx.ReadError:
        # Logger l'erreur mais continuer le flux
        logger.warning(f"Stream interrupted for session {session_id}")
        # Extraire les tokens déjà reçus
        await extract_partial_tokens(response, session_id, metric_id)
```

## Configuration Patterns

### Pattern 8 : Configuration Centralisée
```python
# Toujours utiliser le loader central
from kimi_proxy.config.loader import get_config

config = get_config()
providers = config.get("providers", {})
models = config.get("models", {})

# Expansion variables environnement automatique
toml_content = os.path.expandvars(toml_content)  # ${VAR} → valeur
```

### Pattern 9 : Secrets Management
```python
# config.toml - SEUL endroit pour secrets
[providers."managed:kimi-code"]
api_key = "${KIMI_API_KEY}"  # Variable environnement

# Jamais hardcoder dans le code
```

## Testing Patterns

### Pattern 10 : Async Test Fixtures
```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_database(":memory:")

@pytest.fixture
async def async_client():
    async with AsyncClient(base_url="http://testserver") as client:
        yield client
```

### Pattern 11 : Mock Patching
```python
def test_mcp_timeout(mocker):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.side_effect = httpx.TimeoutException("Timeout")
    client = get_mcp_client()
    with pytest.raises(MCPConnectionError):
        await client.call("compress", {"text": "test"})
```

## Frontend Patterns

### Pattern 12 : ES6 Modules Découplés
```javascript
// static/js/modules/utils.js
export const EventBus = {
    events: new Map(),
    on(event, callback) {
        this.events.get(event)?.add(callback);
    },
    emit(event, data) {
        this.events.get(event)?.forEach(cb => cb(data));
    }
};

// static/js/modules/api.js
import { EventBus } from './utils.js';

export async function createSession(data) {
    const response = await fetch('/api/sessions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    const session = await response.json();
    EventBus.emit('sessionCreated', session);
    return session;
}
```

### Pattern 13 : Named Exports Only
```javascript
// ✅ BON
export function Button() {}

// ❌ MAUVAIS - Pas de default exports
export default function Button() {}
```

## Performance Patterns

### Pattern 14 : Token Counting Précis
```python
# ✅ OBLIGATOIRE - Tiktoken précis
def count_tokens_tiktoken(text: str) -> int:
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# ❌ FORBIDDEN - Estimation incorrecte
def bad_count(text: str) -> int:
    return len(text.split()) * 1.3  # FAUX!
```

### Pattern 15 : Database Access Patterns
```python
# ✅ BON - Context manager
from kimi_proxy.core.database import get_db

with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions")
    rows = cursor.fetchall()

# ❌ MAUVAIS - Connexion globale
connection = sqlite3.connect("sessions.db")  # GLOBAL STATE!
```

## Security Patterns

### Pattern 16 : Workspace Validation MCP
```python
def validate_workspace_access(requested_path: str) -> bool:
    allowed_root = Path(os.environ.get("MCP_WORKSPACE", "/workspace")).resolve()
    requested = Path(requested_path).resolve()
    try:
        requested.relative_to(allowed_root)
        return True
    except ValueError:
        return False  # Path traversal attempt
```

## Memory Management Patterns

### Pattern 17 : MCP Memory Types
```python
# Types standardisés pour mémoire MCP
class MemoryType(Enum):
    FREQUENT = "frequent"    # Patterns récurrents
    EPISODIC = "episodic"    # Conversations
    SEMANTIC = "semantic"     # Vecteurs Qdrant

# Auto-promotion basée sur fréquence d'accès
if access_count > FREQUENT_ACCESS_THRESHOLD:
    memory.type = MemoryType.FREQUENT
```

## Documentation Patterns

### Pattern 18 : Timestamp Format
```markdown
# Format obligatoire pour toutes les entrées
[YYYY-MM-DD HH:MM:SS] - [Summary concise]
```

### Pattern 19 : Cross-References
```markdown
# Références croisées entre fichiers
Voir `decisionLog.md#2026-02-18` pour détails techniques
Référence : `productContext.md#architecture-patterns`
```