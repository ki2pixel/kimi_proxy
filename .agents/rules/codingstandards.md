---
trigger: always_on
description: Kimi Proxy Middleware MCP coding standards - 5-layer architecture, async Python, SSE streaming
globs: ["**/*.py", "**/test_*.py", "**/tests/**/*.py"]
---

# Kimi Proxy Middleware MCP Coding Standards

## Architecture (5 Layers)
```
API (FastAPI) ← Services (SSE/Streaming) ← Features (MCP/Context) ← Proxy (HTTPX Passthrough) ← Core (SQLite MCP Memory)
```

**Rule**: Each layer depends only on layers below. Core has no external dependencies. The application is a pure headless middleware (session-less).

## Python Rules

### Async/Await Mandatory
```python
# ✅ GOOD
import httpx
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        return response.json()

# ❌ BAD - Synchronous I/O
import requests  # FORBIDDEN
def fetch_data(url: str) -> dict:
    response = requests.get(url)  # BLOCKS
    return response.json()
```

### Strict Typing (Limit Any)
```python
# ✅ GOOD
from typing import TypedDict, Dict, Any

class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

def count_tokens(text: str) -> int:
    import tiktoken
    return len(tiktoken.encoding_for_model("gpt-4").encode(text))

def process_payload(data: Dict[str, Any]) -> None:
    # Use Dict[str, Any] only for external JSON payloads
    pass

# ❌ BAD
def bad_function(data: Any) -> Any:  # FORBIDDEN for core domain logic
    return data
```

### HTTPX Resilience & Passthrough
- Use `httpx.AsyncClient()` for all HTTP calls.
- **Mandatory Resilience**: Always handle `httpx.TimeoutException` and `httpx.ReadError` to ensure stable passthrough streaming.
- Configure explicit timeouts and connection pool limits.

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

### Cognitive Complexity & Refactoring (SonarCloud S3776)
- Maintain low cognitive complexity (strictly <= 15 per function).
- Avoid deep nesting (max 3 levels of indentation in business logic).
- Centralize constants and remove unused parameters.
- This rule must be strictly enforced (e.g., maintaining the purity of `proxy.py`, `stream.py`, and `mcp_bridge.py` following Phase 1-3 refactoring).

### Factory Functions & Dependency Injection
```python
# Factory pattern for MCP DB
@contextmanager
def get_mcp_db():
    conn = sqlite3.connect("mcp_memory.db")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# DI pattern for Base URL routing
def get_target_base_url(x_target_base_url: str = Header(...)) -> str:
    return x_target_base_url

@router.post("/chat/completions")
async def proxy_endpoint(target_url: str = Depends(get_target_base_url)):
    # Passthrough logic here
    pass
```

## SSE Streaming Rules (No WebSockets)
- Use `StreamingResponse` with asynchronous generators for Server-Sent Events (SSE).
- Ensure generators are fully non-blocking and yield bytes/strings correctly formatted as `data: {...}\n\n`.
- WebSockets (`/ws`) are deprecated.

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

### French Diagnostic & Logs Mandatory
```python
# ✅ GOOD
@app.get("/health")
def health_check():
    return JSONResponse({
        "status": "opérationnel",
        "message": "Kimi Proxy Middleware MCP est en ligne"
    })
```
- API error messages, system logs, and diagnostic payloads must be in French.

## Anti-Patterns (FORBIDDEN)

### ❌ Global State/Singletons
```python
connection = sqlite3.connect("mcp_memory.db")  # GLOBAL STATE!
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

## Project Structure
```
src/kimi_proxy/
├── main.py              # FastAPI factory
├── core/                # Business logic, no deps
├── config/              # TOML configuration
├── features/            # MCP, sanitizer, compaction
├── proxy/               # HTTP routing (passthrough)
├── services/            # SSE/Streaming manager
└── api/                 # FastAPI routes

tests/unit/              # Isolated tests
memory-bank/             # Context MCP (activeContext.md)
config.toml              # Secrets here only
```

## Key Dependencies
- FastAPI + Uvicorn (async server)
- HTTPX (async HTTP client + Streaming)
- sqlite3 / Qdrant (MCP Memory & Vector Search)
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
Maintain only standard API routes (`/models`, `/chat/completions`) and remove any experimental editor-specific compatibility routes. Do not add additional compatibility prefixes like `/v1/models` without thorough review. Ensure `X-Target-Base-URL` header handles dynamic provider routing.

### Model ID Mapping Simplicity
Keep the model name mapping simple and direct: a) check exact key matches, b) otherwise use suffix split logic. Do not implement JetBrains-specific mappings, complex prefix removals, or fuzzy matching.

### MCP Gateway & Qdrant Integration
- Ensure all insertions to `mcp_memory_entries` and `compaction_history` are asynchronous or properly wrapped.
- Partition context data appropriately for Auto-Memory.

## References
- `README.md` - User docs
- `src/kimi_proxy/core/` - Implementation examples

### Documentation Updates
Any time you create or modify documentation (README, docs/, Markdown guides), you **must** apply the methodology defined in `.agents/skills/documentation/SKILL.md` (TL;DR first, problem-first opening, ❌/✅ blocks, trade-offs, Golden Rule). Treat this skill file as the authoritative checklist before writing.

## Skills Invocation Guide

### Use commit-push Skill (@.agents/skills/commit-push/SKILL.md)
- Commit changes to the current branch and push to remote

### Use debugging-strategies Skill (@.agents/skills/debugging-strategies/SKILL.md)
- Systematic debugging, profiling, root cause analysis for bugs and performance issues

### Use docs-updater Skill (@.agents/skills/docs-updater/SKILL.md)
- Harmoniser la documentation Kimi Proxy en utilisant l'analyse statique standard

### Use documentation Skill (@.agents/skills/documentation/SKILL.md)
- Technical writing, README guidelines, AI-free documentation

### Use end Skill (@.agents/skills/end/SKILL.md)
- Terminer la session et synchroniser la Memory Bank

### Use enhance Skill (@.agents/skills/enhance/SKILL.md)
- Améliorer un Prompt avec le Contexte du Projet Kimi Proxy Middleware MCP

### Use enhance-complex Skill (@.agents/skills/enhance-complex/SKILL.md)
- Analyse profonde, Planification Shrimp Task Manager et Réflexion Séquentielle

### Use fast-filesystem Skill (@.agents/skills/fast-filesystem-ops/SKILL.md)
- Fast file system operations for efficient file management

### Use json-query-expert Skill (@.agents/skills/json-query-expert/SKILL.md)
- JSON Query Expert for efficient data extraction and manipulation

### Use kimi-proxy-config-manager Skill (@.agents/skills/kimi-proxy-config-manager/SKILL.md)
- TOML/YAML config management, provider routing, API key setup

### Use kimi-proxy-mcp-integration Skill (@.agents/skills/kimi-proxy-mcp-integration/SKILL.md)
- MCP servers, memory management, semantic search, Phase 2-4 features

### Use kimi-proxy-performance-optimization Skill (@.agents/skills/kimi-proxy-performance-optimization/SKILL.md)
- Token counting, database queries, WebSocket performance, caching

### Use kimi-proxy-streaming-debug Skill (@.agents/skills/kimi-proxy-streaming-debug/SKILL.md)
- Streaming errors: ReadError, Timeout, ConnectError, SSE issues

### Use kimi-proxy-testing-strategies Skill (@.agents/skills/kimi-proxy-testing-strategies/SKILL.md)
- Unit tests, integration, E2E, performance testing with pytest-asyncio

### Use sequentialthinking-logic Skill (@.agents/skills/sequentialthinking-logic/SKILL.md)
- Sequential Thinking Logic for complex architecture and extension logic

### Use shrimp-task-manager Skill (@.agents/skills/shrimp-task-manager/SKILL.md)
- Task management with Shrimp Task Manager

## Database Schema Extensions (Phase 3 MCP)

### New Tables Added
- `mcp_memory_entries` - Standardized MCP memory storage
- `mcp_compression_results` - Algorithmic compression results
- `mcp_routing_decisions` - Context-aware routing decisions
- `compaction_history` - Context compaction history

## New Features (Recent Evolutions)

### Context Compaction (Phase 1)
- Automatic context reduction infrastructure
- Intelligent history trimming based on relevance

### Auto Memory (Phase 2)
- Pattern detection and storage in conversations
- Automatic promotion of frequent/episodic/semantic patterns

### MCP Standard (Phase 3)
- Complete MCP server integration
- External tool orchestration (Qdrant, Compression servers)

### Log Watcher
- Real-time PyCharm/Continue monitoring
- CompileChat block parsing and integration

## Performance Patterns

### VACUUM Optimization
```python
def vacuum_database() -> Dict[str, Any]:
    """Cache-integrated VACUUM to avoid repeated expensive operations (30s min)"""
    if current_time - last_vacuum < 30:
        return {"skipped": True}  # Avoid costly operations
```

For Kimi Proxy development: Use primary skill + reference this file for unified conventions.

---
**Version 2.9** - **< 10000 chars**