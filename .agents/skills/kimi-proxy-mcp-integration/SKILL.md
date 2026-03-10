---
name: kimi-proxy-mcp-integration
description: Comprehensive MCP (Model Context Protocol) integration for Kimi Proxy Dashboard. Use when working with MCP servers, memory management, semantic search, or external tool integration. Covers Phase 2-5 MCP features including Shrimp Task Manager, Sequential Thinking, Fast Filesystem, JSON Query, and Gateway servers.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy MCP Integration

**TL;DR**: The MCP stack combines standardized memory storage, Qdrant/compression clients, gateway-based external server access, and newer context-management features such as compaction and auto-memory. Document the real façade, DB tables, and error classes first; treat server-specific tool lists as runtime contracts that must be verified against the current bridge/gateway configuration.

## Source of Truth

Primary backend files:

- `src/kimi_proxy/features/mcp/client.py`
- `src/kimi_proxy/features/mcp/base/config.py`
- `src/kimi_proxy/features/mcp/base/rpc.py`
- `src/kimi_proxy/features/mcp/memory.py`
- `src/kimi_proxy/core/database.py`
- `src/kimi_proxy/api/routes/mcp.py`
- `src/kimi_proxy/api/routes/mcp_gateway.py`
- `src/kimi_proxy/features/log_watcher/*`
- `src/kimi_proxy/features/compaction/*`

## Phase Alignment

### Phase 1: Context compaction

- `compaction_history` table in SQLite
- `features/compaction/simple_compaction.py`
- `features/compaction/auto_trigger.py`
- WebSocket compaction events broadcast from storage / API routes

### Phase 2: Auto-memory and session-aware memory metrics

- memory metrics in `metrics`, `memory_metrics`, `memory_segments`
- auto-memory broadcasts such as `auto_memory_stored`
- advanced memory stats surfaced in API and dashboard modules

### Phase 3: Standardized MCP persistence

Current schema extensions include:

- `mcp_memory_entries`
- `mcp_compression_results`
- `mcp_routing_decisions`
- `compaction_history`

### Phase 4–5: External MCP ecosystem and gateway

- gateway route: `/api/mcp-gateway/{server_name}/rpc`
- configured server families include `shrimp-task-manager`, `sequential-thinking`, `fast-filesystem`, `json-query`
- stdio / bridge compatibility is part of the operational model

## Current Backend Capabilities

### Specialized façade

`MCPExternalClient` currently provides first-class wrappers for:

- Qdrant semantic search
- compression server operations
- chunking / caching helpers for large MCP responses

It also exposes generic compatibility surfaces, but you should not assume every high-level helper method exists for every external server unless you verify the current code or gateway behavior.

### ✅ Real low-level RPC pattern

```python
from kimi_proxy.features.mcp.base.rpc import MCPRPCClient

client = MCPRPCClient()
result = await client.make_rpc_call(
    "http://localhost:8004",
    "tools/list",
    {},
    timeout_ms=5000.0,
)
```

## Error Handling

The current canonical MCP exceptions are defined in `src/kimi_proxy/features/mcp/base/rpc.py`:

- `MCPClientError`
- `MCPConnectionError`
- `MCPTimeoutError`

### ✅ Current handling pattern

```python
from kimi_proxy.features.mcp.base.rpc import (
    MCPRPCClient,
    MCPClientError,
    MCPConnectionError,
    MCPTimeoutError,
)

try:
    result = await client.make_rpc_call(server_url, method, params)
except MCPTimeoutError:
    ...
except MCPConnectionError:
    ...
except MCPClientError:
    ...
```

## Memory Management

`src/kimi_proxy/features/mcp/memory.py` is the real standardized memory manager.

It supports:

- storing episodic / frequent / semantic memories
- de-duplication via content hash
- Qdrant-backed semantic storage when available
- promotion of frequent patterns
- cleanup of old episodic memories
- optional compression of large memories when beneficial

### ✅ Real storage pattern

```python
from kimi_proxy.features.mcp.memory import get_memory_manager

manager = get_memory_manager()
entry = await manager.store_memory(
    session_id=123,
    content="Important context",
    memory_type="episodic",
    metadata={"source": "manual"},
)
```

## Gateway and External Servers

The project exposes gateway-backed MCP access through `/api/mcp-gateway/.../rpc` and server-status APIs under `/api/memory/*`.

Documented external server families should stay limited to the ones already recognized by the codebase:

- `shrimp-task-manager`
- `sequential-thinking`
- `fast-filesystem`
- `json-query`

### Important caution

Do not hardcode tool-specific examples such as `initialize_project`, `expand_task`, `batch_file_operations`, or `json_query_jsonpath` as guaranteed Python façade methods unless you have revalidated them against the current gateway/bridge/server contract. Prefer gateway- or RPC-level examples when writing durable docs.

## Log Watcher Integration

MCP-related context features now coexist with a richer analytics pipeline.

`src/kimi_proxy/main.py` starts `create_log_watcher(...)` and broadcasts normalized log-derived metrics to the dashboard. This is relevant for MCP documentation because:

- auto-session decisions may correlate provider/model/session metadata
- memory and compaction UI receive live updates alongside proxy metrics
- health endpoints surface log watcher state and sources

## Database Schema Notes

When touching MCP documentation, keep these schema facts synchronized:

- `mcp_memory_entries`: canonical SQLite store for frequent/episodic memory payloads and metadata
- `mcp_compression_results`: persisted compression results
- `mcp_routing_decisions`: routing or fallback reasoning metadata
- `compaction_history`: context compaction history, including trigger reason and savings

## ❌ Outdated Documentation Patterns to Avoid

- Presenting Phase 4 external tools as fully wrapped Python helper methods if only gateway/RPC access is guaranteed
- Omitting current SQLite schema tables introduced after the original Phase 3 write-up
- Ignoring `MCPClientError` / `MCPConnectionError` / `MCPTimeoutError`
- Treating log watcher analytics as unrelated to the current MCP/auto-session ecosystem

## Golden Rule

**Document MCP features at the level the code actually guarantees today: schema, RPC, façade, gateway, and error handling.** Treat individual external-tool verbs as runtime-validated contracts, not timeless static APIs.