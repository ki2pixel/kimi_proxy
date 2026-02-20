---
name: condingstardards
description: Kimi Proxy Dashboard coding standards - 5-layer architecture, async Python, ES6 modules
globs: ["**/*.py", "**/*.js", "**/*.html", "**/test_*.py", "**/tests/**/*.py"]
alwaysApply: true
---

# Kimi Proxy Coding Standards

## Architecture (5 Layers)
```
API (FastAPI) ← Services (WebSocket) ← Features (MCP) ← Proxy (HTTPX) ← Core (SQLite)
```

**Rule**: Each layer depends only on layers below. Core has no external dependencies.

## Python Rules

### Async/Await Mandatory
```python
# ✅ GOOD
import httpx
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ BAD - Synchronous I/O
import requests  # FORBIDDEN
def fetch_data(url: str) -> dict:
    response = requests.get(url)  # BLOCKS
    return response.json()
```

### Strict Typing (No Any)
```python
# ✅ GOOD
from typing import TypedDict

class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

def count_tokens(text: str) -> int:
    import tiktoken
    return len(tiktoken.encoding_for_model("gpt-4").encode(text))

# ❌ BAD
def bad_function(data: Any) -> Any:  # FORBIDDEN
    return data
```

### HTTPX Only (No Requests)
- Use `httpx.AsyncClient()` for all HTTP calls

### Tiktoken for Token Counting
```python
# ✅ OBLIGATORY - Precise counting
def count_tokens_tiktoken(text: str) -> int:
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# ❌ FORBIDDEN - Estimation
def bad_count(text: str) -> int:
    return len(text.split()) * 1.3  # WRONG!
```

### Factory Functions & Dependency Injection
```python
# Factory pattern
@contextmanager
def get_db():
    conn = sqlite3.connect("sessions.db")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# DI pattern
def get_connection_manager() -> ConnectionManager:
    return manager

@router.websocket("/ws")
async def endpoint(manager: ConnectionManager = Depends(get_connection_manager)):
    await manager.connect(websocket)
```

## Frontend Rules

### ES6 Modules (No Bundlers)
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

### Vanilla JS (No Frameworks)
- No React, Vue, or heavy frameworks
- Event bus for decoupling

## Testing Rules

### Async Test Fixtures
```python
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_database(":memory:")

@pytest.fixture
async def async_client():
    async with AsyncClient(base_url="http://testserver") as client:
        yield client
```

### Mock Patching
```python
def test_mcp_timeout(mocker):
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.side_effect = httpx.TimeoutException("Timeout")
    client = get_mcp_client()
    with pytest.raises(MCPConnectionError):
        await client.call("compress", {"text": "test"})
```

- **pytest-asyncio** for async tests
- **Memory DB** for unit tests

## Security Rules

### No Hardcoded Secrets
```toml
# config.toml - ONLY place for secrets
[providers."managed:kimi-code"]
api_key = "${KIMI_API_KEY}"  # Environment variable
```

```python
# src/kimi_proxy/config/loader.py
import os
toml_content = os.path.expandvars(toml_content)  # Expand ${VAR}
config = tomlkit.parse(toml_content)
```

### MCP Workspace Validation
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

## Language Rules

### French UI Text Mandatory
```python
@app.get("/health")
def health_check():
    return JSONResponse({
        "status": "opérationnel",
        "message": "Kimi Proxy Dashboard est en ligne"
    })
```

```javascript
const STATUS_LABELS = {
    active: 'Actif',
    idle: 'Inactif',
    error: 'Erreur'
};
```

## Anti-Patterns (FORBIDDEN)

### ❌ Global State/Singletons
```python
connection = sqlite3.connect("sessions.db")  # GLOBAL STATE!
```

### ❌ Circular Imports
```python
from kimi_proxy.api.routes.sessions import get_session  # CIRCULAR!

# ✅ GOOD
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from kimi_proxy.api.routes.sessions import SessionResponse
```

### ❌ Silent Try/Catch
```python
try:
    await process_data()
except Exception:
    pass  # BUGS HIDDEN!
```

### ❌ Synchronous I/O
```python
import requests
response = requests.get(url)  # BLOCKS EVENT LOOP
```

### ❌ Default Exports
```javascript
export default function Button() {}  # NO DEFAULTS
export function Button() {}  # NAMED EXPORT
```

## Project Structure
```
src/kimi_proxy/
├── main.py              # FastAPI factory
├── core/                # Business logic, no deps
├── config/              # TOML configuration
├── features/            # MCP, sanitizer
├── proxy/               # HTTP routing
├── services/            # WebSocket manager
└── api/                 # FastAPI routes

static/js/modules/       # ES6 modules
tests/unit/              # Isolated tests
config.toml             # Secrets here only
```

## Key Dependencies
- FastAPI + Uvicorn (async server)
- HTTPX (async HTTP client)
- aiosqlite (async SQLite)
- tiktoken (token counting)
- pytest-asyncio (async tests)

## Commands
```bash
./bin/kimi-proxy start --reload  # Dev server
./bin/kimi-proxy test            # Run tests
./scripts/start-mcp-servers.sh start  # MCP servers
```

## File-Specific Rules

### Clean API Router Structure

Maintain only standard API routes (/models, /chat/completions) and remove any experimental editor-specific compatibility routes. Do not add additional compatibility prefixes like /v1/models or routes similar to Ollama without thorough review.

### Model ID Mapping Simplicity

Keep the model name mapping simple and direct: a) check exact key matches, b) otherwise use suffix split logic. Do not implement JetBrains-specific mappings, complex prefix removals, or fuzzy matching.

## References
- `README.md` - User docs
- `src/kimi_proxy/core/` - Implementation examples

### Documentation Updates
Any time you create or modify documentation (README, docs/, Markdown guides), you **must** apply the methodology defined in `.windsurf/skills/documentation/SKILL.md` (TL;DR first, problem-first opening, ❌/✅ blocks, trade-offs, Golden Rule). Treat this skill file as the authoritative checklist before writing.

## Skills Invocation Guide

### Use debugging-strategies Skill (@.continue/rules/debugging-strategies.md)
- Systematic debugging techniques, profiling tools, and root cause analysis
- Tracking down elusive bugs, investigating performance issues, understanding unfamiliar codebases
- Debugging production issues, analyzing crash dumps and stack traces
- Debugging distributed systems

### Use documentation Skill (@.continue/rules/documentation.md)
- Technical writing, README guidelines, and punctuation rules
- Writing documentation, READMEs, technical articles, or any prose that should avoid AI-generated feel

### Use kimi-proxy-config-manager Skill (@.continue/rules/kimi-proxy-config-manager.md)
- Managing TOML/YAML configurations, adding new providers, setting up API keys
- Troubleshooting configuration issues, provider routing, model mappings
- Environment variable integration

### Use kimi-proxy-frontend-architecture Skill (@.continue/rules/kimi-proxy-frontend-architecture.md)
- Working with real-time dashboard, ES6 modules, Chart.js visualizations
- WebSocket-based live updates, modular frontend architecture
- Performance optimization for frontend

### Use kimi-proxy-mcp-integration Skill (@.continue/rules/kimi-proxy-mcp-integration.md)
- MCP servers integration, memory management, semantic search
- External tool integration, Phase 2-4 MCP features
- Task Master, Sequential Thinking, Fast Filesystem, JSON Query servers

### Use kimi-proxy-performance-optimization Skill (@.continue/rules/kimi-proxy-performance-optimization.md)
- Optimizing token counting, database queries, WebSocket performance
- Reducing latency, async optimization, database indexing
- Caching strategies, resource utilization

### Use kimi-proxy-streaming-debug Skill (@.continue/rules/kimi-proxy-streaming-debug.md)
- Debugging streaming errors: ReadError, TimeoutException, ConnectError
- SSE streaming issues, proxy streaming failures
- Token extraction problems, WebSocket connection issues

### Use kimi-proxy-testing-strategies Skill (@.continue/rules/kimi-proxy-testing-strategies.md)
- Writing tests, debugging issues, ensuring system reliability
- Unit tests, integration tests, E2E testing, performance testing
- pytest-asyncio strategies

### Use taskmaster Skill (@.continue/rules/taskmaster.md)
- Task management with Taskmaster MCP tools and CLI commands
- Project planning, task expansion, complexity analysis

For Kimi Proxy development: Use primary skill + reference this file for unified conventions.

---
**Version 2.6** - **< 10000 chars**