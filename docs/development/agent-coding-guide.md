# 🤖 Guide de Codage pour Agents IA - Kimi Proxy Dashboard

**TL;DR**: Ce guide est optimisé pour les agents IA travaillant sur le projet Kimi Proxy Dashboard. Il complète les standards de codage avec des exemples pratiques et patterns spécifiques au projet.

## Pourquoi ce guide existe

Les agents IA ont besoin de plus que des règles - ils ont besoin d'exemples concrets et de patterns éprouvés. Ce guide fournit le "comment" alors que `codingstandards.md` fournit le "quoi".

## Architecture 5 Couches - Exemples Pratiques

### Core Layer (Pas de dépendances externes)

```python
# src/kimi_proxy/core/tokens.py
from typing import TypedDict
import tiktoken

class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

def count_tokens_tiktoken(text: str) -> int:
    """Comptage précis des tokens - OBLIGATOIRE"""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# ✅ BON - Factory pattern
@contextmanager
def get_db():
    conn = sqlite3.connect("sessions.db")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# ❌ MAUVAIS - Global state
connection = sqlite3.connect("sessions.db")  # FORBIDDEN!
```

### Features Layer (Dépendances Core + Config)

```python
# src/kimi_proxy/features/sanitizer.py
from kimi_proxy.core.tokens import count_tokens_tiktoken
from kimi_proxy.config.settings import get_settings

class ContentSanitizer:
    def __init__(self, settings: Settings = Depends(get_settings)):
        self.min_token_threshold = settings.sanitizer.min_tokens
    
    async def should_mask_content(self, content: str) -> bool:
        """Détection automatique contenu verbeux"""
        token_count = count_tokens_tiktoken(content)
        return token_count > self.min_token_threshold
```

### Services Layer (Dépendances toutes sauf API)

```python
# src/kimi_proxy/services/websocket_manager.py
from typing import Set, Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_data: Dict[WebSocket, dict] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.connection_data[websocket] = {"session_id": session_id}
    
    async def broadcast(self, message: dict):
        """Broadcast temps réel à tous les clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                # Gérer déconnexion gracieuse
                self.active_connections.discard(connection)
```

### API Layer (Peut importer tout)

```python
# src/kimi_proxy/api/routes/sessions.py
from fastapi import APIRouter, Depends, WebSocket
from kimi_proxy.services.websocket_manager import ConnectionManager
from kimi_proxy.core.models import SessionCreate

router = APIRouter()

def get_connection_manager() -> ConnectionManager:
    return ConnectionManager()

@router.post("/sessions")
async def create_session(
    session_data: SessionCreate,
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """Création session avec injection dépendances"""
    session = await create_session_db(session_data)
    await manager.broadcast({"type": "session_created", "data": session})
    return session
```

## Patterns Anti-Patterns - Exemples Concrets

### ✅ Async/Await Correct

```python
# src/kimi_proxy/proxy/client.py
import httpx
from typing import Dict, Any

async def make_llm_request(url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Requête HTTP async - OBLIGATOIRE"""
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, timeout=30.0)
        response.raise_for_status()
        return response.json()

# ❌ INTERDIT - I/O synchrone
import requests  # FORBIDDEN
def bad_request(url: str, data: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(url, json=data)  # BLOCKS EVENT LOOP!
    return response.json()
```

### ✅ Typage Strict

```python
from typing import TypedDict, List, Optional
from dataclasses import dataclass

@dataclass
class SessionMetric:
    session_id: str
    input_tokens: int
    output_tokens: int
    provider: str
    created_at: datetime
    
class SessionResponse(TypedDict):
    id: str
    metrics: List[SessionMetric]
    status: str
    provider: Optional[str]

# ❌ INTERDIT - Any typing
def bad_function(data: Any) -> Any:  # FORBIDDEN
    return data
```

### ✅ Gestion Erreurs Structurée

```python
# src/kimi_proxy/core/exceptions.py
class StreamingError(Exception):
    def __init__(self, message: str, provider: str, error_type: str, retry_count: int = 0):
        self.provider = provider
        self.error_type = error_type
        self.retry_count = retry_count
        super().__init__(message)

# src/kimi_proxy/proxy/stream.py
async def handle_streaming_response(response: httpx.Response, provider: str):
    try:
        async for chunk in response.aiter_bytes():
            yield chunk
    except httpx.ReadError as e:
        raise StreamingError(f"Connection lost: {e}", provider, "ReadError")
    except Exception as e:
        # ❌ INTERDIT - Silent catch
        pass  # BUGS HIDDEN!
```

## Frontend - ES6 Modules

### ✅ Modules Découplés

```javascript
// static/js/modules/utils.js
export const EventBus = {
    events: new Map(),
    on(event, callback) {
        if (!this.events.has(event)) {
            this.events.set(event, new Set());
        }
        this.events.get(event).add(callback);
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

// ❌ INTERDIT - Default exports
export default function Button() {}  // NO DEFAULTS
export function Button() {}  # NAMED EXPORT
```

### ✅ Event Bus Pattern

```javascript
// static/js/modules/websocket.js
import { EventBus } from './utils.js';

class WebSocketManager {
    constructor(url) {
        this.ws = new WebSocket(url);
        this.setupEventHandlers();
    }
    
    setupEventHandlers() {
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            EventBus.emit('websocket:message', data);
        };
        
        this.ws.onclose = () => {
            EventBus.emit('websocket:disconnected');
        };
    }
}

export { WebSocketManager };
```

## Tests - Async Fixtures

### ✅ Tests Async Corrects

```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Base de données mémoire pour tous les tests"""
    init_database(":memory:")

@pytest.fixture
async def async_client():
    """Client HTTP async pour les tests"""
    async with AsyncClient(base_url="http://testserver") as client:
        yield client

# tests/unit/test_tokens.py
def test_token_counting():
    """Test comptage précis des tokens"""
    text = "Hello, world!"
    count = count_tokens_tiktoken(text)
    assert count == 4  # Tiktoken cl100k_base

# tests/integration/test_proxy.py
@pytest.mark.asyncio
async def test_proxy_streaming(async_client):
    """Test streaming avec retry"""
    response = await async_client.post("/chat/completions", json=test_data)
    assert response.status_code == 200
```

### ✅ Mock Patching

```python
# tests/unit/test_mcp_client.py
def test_mcp_timeout(mocker):
    """Test timeout MCP avec mock"""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.side_effect = httpx.TimeoutException("Timeout")
    
    client = get_mcp_client()
    with pytest.raises(MCPConnectionError):
        await client.call("compress", {"text": "test"})
```

## Sécurité - Patterns Essentiels

### ✅ Configuration Sécurisée

```toml
# config.toml - SEULEMENT endroit pour les secrets
[providers."managed:kimi-code"]
api_key = "${KIMI_API_KEY}"  # Variable d'environnement

[providers."managed:nvidia"]
api_key = "${NVIDIA_API_KEY}"
```

```python
# src/kimi_proxy/config/loader.py
import os
import tomlkit

def load_config() -> dict:
    """Chargement config avec expansion variables"""
    with open("config.toml") as f:
        toml_content = f.read()
    
    # Expand ${VAR} vers variables d'environnement
    toml_content = os.path.expandvars(toml_content)
    return tomlkit.parse(toml_content)
```

### ✅ Validation Workspace MCP

```python
# src/kimi_proxy/features/mcp/client.py
from pathlib import Path
import os

def validate_workspace_access(requested_path: str) -> bool:
    """Validation sécurité accès workspace MCP"""
    allowed_root = Path(os.environ.get("MCP_WORKSPACE", "/workspace")).resolve()
    requested = Path(requested_path).resolve()
    
    try:
        requested.relative_to(allowed_root)
        return True
    except ValueError:
        return False  # Tentative path traversal
```

## Patterns Spécifiques Projet

### ✅ Log Watcher Integration

```python
# src/kimi_proxy/features/log_watcher/watcher.py
class LogWatcher:
    def __init__(self, log_path: str, websocket_manager: ConnectionManager):
        self.log_path = Path(log_path)
        self.websocket_manager = websocket_manager
        self.last_position = 0
    
    async def watch_log_file(self):
        """Surveillance temps réel fichier logs Continue.dev"""
        while True:
            try:
                if self.log_path.exists():
                    new_content = await self._read_new_lines()
                    if new_content:
                        metrics = self._parse_compilechat_blocks(new_content)
                        await self.websocket_manager.broadcast({
                            "type": "log_metrics",
                            "data": metrics
                        })
                await asyncio.sleep(1)  # Polling interval
            except Exception as e:
                logger.error(f"Log watcher error: {e}")
                await asyncio.sleep(5)  # Backoff on error
```

### ✅ Smart Routing Pattern

```python
# src/kimi_proxy/proxy/router.py
class SmartRouter:
    def __init__(self):
        self.providers = load_providers()
        self.routing_weights = {
            "context_capacity": 0.4,
            "cost_per_token": 0.3,
            "latency": 0.2,
            "reliability": 0.1
        }
    
    def find_optimal_provider(self, context_tokens: int) -> str:
        """Sélection provider optimale basée sur contexte restant"""
        scores = {}
        
        for provider_id, provider in self.providers.items():
            if provider.context_limit >= context_tokens:
                score = (
                    provider.context_limit * self.routing_weights["context_capacity"] +
                    (1 / provider.cost_per_token) * self.routing_weights["cost_per_token"] +
                    (1 / provider.latency) * self.routing_weights["latency"]
                )
                scores[provider_id] = score
        
        return max(scores, key=scores.get) if scores else self.get_fallback_provider()
```

## Références et Standards

- **Standards autoritatifs** : `.windsurf/rules/codingstandards.md`
- **Architecture détaillée** : `docs/architecture/modular-architecture-v2.md`
- **Fonctionnalités** : `docs/features/`
- **Tests** : `tests/unit/`, `tests/integration/`, `tests/e2e/`

## Commandes Essentielles

```bash
# Développement
./bin/kimi-proxy start --reload  # Dev server
./bin/kimi-proxy test            # Run tests
./scripts/start-mcp-servers.sh start  # MCP servers

# Tests
PYTHONPATH=src python -m pytest tests/ -v
PYTHONPATH=src python -m pytest tests/unit/ -v --cov=src

# Linting (si configuré)
black src/ tests/
mypy src/
```

---

*Ce guide complète les standards de codage avec des exemples pratiques pour les agents IA travaillant sur Kimi Proxy Dashboard.*

*Version: 1.0.0*
*Dernière mise à jour: Février 2026*
