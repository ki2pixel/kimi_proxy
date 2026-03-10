---
name: kimi-proxy-performance-optimization
description: Performance optimization expert for Kimi Proxy Dashboard. Use when optimizing token counting, database queries, WebSocket performance, or reducing latency. Covers async optimization, database indexing, caching strategies, and resource utilization.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Performance Optimization

**TL;DR**: Focus on the optimizations that are already in production: HTTPX connection reuse, MCP response chunking/cache, throttled database `VACUUM`, existing SQLite indexes, and lightweight WebSocket broadcast cleanup. Do not document speculative helpers as if they were live code.

## Source of Truth

Key implementation files:

- `src/kimi_proxy/features/mcp/base/rpc.py`
- `src/kimi_proxy/features/mcp/client.py`
- `src/kimi_proxy/core/database.py`
- `src/kimi_proxy/services/websocket_manager.py`
- `src/kimi_proxy/proxy/stream.py`
- `src/kimi_proxy/proxy/client.py`

## Current Performance Hotspots

### 1. Token counting

Use the project token helpers and keep exact counting.

- prefer `count_tokens_tiktoken(...)` or `count_tokens_text(...)`
- do not reintroduce heuristic word-count approximations

### 2. MCP payload size

Large MCP outputs are already handled through:

- `chunk_large_response(...)`
- `should_chunk_response(...)`
- in-memory chunk cache
- tool-result cache for selected heavy filesystem / JSON operations

### 3. SQLite maintenance

The current code includes schema indexes and a throttled `vacuum_database()` helper.

### 4. WebSocket broadcast fan-out

`ConnectionManager.broadcast()` is intentionally simple: sequential send, collect broken sockets, then clean them up.

## Existing Optimizations You Should Preserve

### HTTPX pooling in MCP RPC

```python
from kimi_proxy.features.mcp.base.rpc import MCPRPCClient

client = MCPRPCClient()
```

`MCPRPCClient` keeps an `httpx.AsyncClient` with configured connection limits and timeouts. Reuse this pattern instead of creating throwaway clients in tight loops.

### Large MCP response chunking and cache

```python
from kimi_proxy.features.mcp.client import chunk_large_response, should_chunk_response
```

This is the real large-response mitigation in the codebase today. If you need to optimize Filesystem or JSON-query traffic, start here.

### Throttled database VACUUM

`src/kimi_proxy/core/database.py::vacuum_database()` already prevents repeated expensive `VACUUM` calls by enforcing a 30-second minimum interval.

```python
from kimi_proxy.core.database import vacuum_database

result = vacuum_database()
```

This helper is also invoked after bulk session deletions.

### WebSocket cleanup-on-broadcast

```python
from kimi_proxy.services.websocket_manager import get_connection_manager

manager = get_connection_manager()
await manager.broadcast({"type": "metric_updated", "session_id": 1})
```

The current manager is not queue-based. It favors straightforward cleanup and small JSON payloads.

## Token Counting Guidance

### ✅ Document what exists

- exact token counting via project helpers
- post-stream reconciliation via `proxy/stream.py`
- cumulative and latest-token calculations in `core/database.py`

### ❌ Do not document as production features unless they land in code

- `cached_token_count`
- `StreamingTokenCounter`
- `MemoryProfiler`
- Redis-style TTL caches
- queued WebSocket workers

Those may be valid future ideas; they are not part of the current production implementation.

## Database Guidance

The SQLite layer is currently synchronous and context-manager based. Optimize within that constraint unless the architecture explicitly changes.

Existing persisted performance-related structures include:

- indexes on `mcp_memory_entries`
- compaction counters on `sessions`
- stored token metrics in `metrics`

When documenting queries, prefer the actual helpers already used by the app:

- `get_session_total_tokens()`
- `get_session_cumulative_tokens()`
- `get_session_stats()`
- `vacuum_database()`

## Streaming and Broadcast Performance

`proxy/stream.py` performs best-effort token extraction after streaming and emits compact WebSocket updates such as `metric_updated` and `streaming_error`.

Optimization rule: keep payloads small and typed; let the frontend derive presentation state from events rather than sending oversized UI-specific blobs.

## Measurement Guidance

Prefer measuring real hotspots with the existing stack:

```bash
sqlite3 sessions.db 'EXPLAIN QUERY PLAN SELECT * FROM metrics WHERE session_id = 1 ORDER BY timestamp DESC LIMIT 50;'
PYTHONPATH=src python -m pytest tests/mcp/test_mcp_compression.py -q
```

## Golden Rule

**Describe the optimizations that the code already applies, and label everything else as a candidate pattern rather than current architecture.** This skill should reduce drift, not create imaginary performance infrastructure.