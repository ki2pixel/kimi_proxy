---
name: kimi-proxy-mcp-integration
description: Comprehensive MCP (Model Context Protocol) integration for Kimi Proxy Dashboard. Use when working with MCP servers, memory management, semantic search, or external tool integration. Covers Phase 2-4 MCP features including Task Master, Sequential Thinking, Fast Filesystem, and JSON Query servers.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy MCP Integration

This skill provides comprehensive MCP integration guidance for Kimi Proxy Dashboard.

## MCP Architecture Overview

### MCP Phases

**Phase 2**: Memory detection and standardization
- Detects `<mcp-memory>`, `@memory[]`, `@recall()` tags
- Distinguishes frequent/episodic/semantic memory types

**Phase 3**: External MCP servers
- Qdrant MCP: Semantic search (<50ms)
- Context Compression MCP: Advanced compression

**Phase 4**: Extended MCP ecosystem
- Task Master MCP (14 tools): Task management
- Sequential Thinking MCP (1 tool): Structured reasoning
- Fast Filesystem MCP (25 tools): File operations
- JSON Query MCP (3 tools): JSON querying

## MCP Server Management

### Starting MCP Servers

```bash
# Start all MCP servers automatically
./scripts/start-mcp-servers.sh start

# Start individual servers
./scripts/start-mcp-servers.sh start-task-master
./scripts/start-mcp-servers.sh start-sequential-thinking
./scripts/start-mcp-servers.sh start-filesystem
./scripts/start-mcp-servers.sh start-json-query

# Check server status
./scripts/start-mcp-servers.sh status
```

### Server Configuration

```toml
# config.toml MCP configuration
[mcp.task_master]
enabled = true
url = "http://localhost:8002"
timeout_ms = 30000

[mcp.sequential_thinking]
enabled = true
url = "http://localhost:8003"
timeout_ms = 60000

[mcp.fast_filesystem]
enabled = true
url = "http://localhost:8004"
timeout_ms = 10000
workspace_path = "/home/kidpixel/kimi-proxy"

[mcp.json_query]
enabled = true
url = "http://localhost:8005"
timeout_ms = 5000
```

### Server Health Monitoring

```bash
# Check all MCP servers
curl http://localhost:8000/api/memory/all-servers

# Check Phase 4 servers specifically
curl http://localhost:8000/api/memory/servers/phase4

# Monitor server status
watch -n 5 'curl -s http://localhost:8000/api/memory/all-servers | jq ".servers[].status"'
```

## Task Master MCP Integration

### Task Management Workflow

```python
# Initialize Task Master project
from kimi_proxy.features.mcp.client import get_mcp_client

client = get_mcp_client("task_master")
await client.call("initialize_project", {
    "projectRoot": "/home/kidpixel/kimi-proxy",
    "skipInstall": False,
    "addAliases": True,
    "initGit": True,
    "storeTasksInGit": True,
    "yes": True
})
```

### Common Task Master Operations

```bash
# Parse PRD to generate tasks
curl -X POST http://localhost:8000/api/memory/task-master/parse-prd \
  -H "Content-Type: application/json" \
  -d '{"input": "/home/kidpixel/kimi-proxy/.shrimp-task-manager/plan/prd.txt", "projectRoot": "/home/kidpixel/kimi-proxy", "force": true}'

# Get all tasks
curl http://localhost:8000/api/memory/task-master/tasks

# Analyze project complexity
curl -X POST http://localhost:8000/api/memory/task-master/analyze-complexity \
  -H "Content-Type: application/json" \
  -d '{"projectRoot": "/home/kidpixel/kimi-proxy", "threshold": 5, "research": true}'
```

### Task Expansion

```python
# Expand a task into subtasks
await client.call("expand_task", {
    "id": "1",
    "research": true,
    "projectRoot": "/home/kidpixel/kimi-proxy",
    "force": False,
    "num": "5"
})
```

## Sequential Thinking MCP

### Structured Reasoning

```python
# Use sequential thinking for complex problems
client = get_mcp_client("sequential_thinking")

result = await client.call("sequentialthinking_tools", {
    "available_mcp_tools": ["task-master", "filesystem", "json-query"],
    "thought": "I need to debug a streaming error in the proxy. Let me analyze the error patterns systematically.",
    "next_thought_needed": True,
    "thought_number": 1,
    "total_thoughts": 5
})
```

### Problem-Solving Pattern

```bash
# Example: Debug streaming issues
curl -X POST http://localhost:8000/api/memory/sequential-thinking/call \
  -H "Content-Type: application/json" \
  -d '{
    "available_mcp_tools": ["task-master", "filesystem"],
    "thought": "I need to investigate the ReadError in streaming. First, I should check the logs for error patterns.",
    "next_thought_needed": true,
    "thought_number": 1,
    "total_thoughts": 4
  }'
```

## Fast Filesystem MCP

### File Operations

```python
# High-performance file operations
client = get_mcp_client("fast_filesystem")

# Read multiple files efficiently
files = await client.call("read_multiple_files", {
    "paths": [
        "/home/kidpixel/kimi-proxy/config.toml",
        "/home/kidpixel/kimi-proxy/README.md",
        "/home/kidpixel/kimi-proxy/src/kimi_proxy/main.py"
    ]
})

# Search files with patterns
results = await client.call("search_files", {
    "path": "/home/kidpixel/kimi-proxy/src",
    "pattern": "*.py",
    "content_search": True,
    "max_results": 50
})
```

### Directory Management

```python
# Get directory tree
tree = await client.call("get_directory_tree", {
    "path": "/home/kidpixel/kimi-proxy",
    "max_depth": 3,
    "include_files": True
})

# Create directories
await client.call("create_directory", {
    "path": "/home/kidpixel/kimi-proxy/new-feature",
    "recursive": True
})
```

## JSON Query MCP

### Advanced JSON Operations

```python
# Query JSON files with JSONPath
client = get_mcp_client("json_query")

# Extract specific data
result = await client.call("json_query_jsonpath", {
    "file_path": "/home/kidpixel/kimi-proxy/config.toml",
    "jsonpath": "$.providers.*.api_key"
})

# Search for keys
keys = await client.call("json_query_search_keys", {
    "file_path": "/home/kidpixel/kimi-proxy/sessions.db",
    "query": "token",
    "limit": 10
})
```

## Memory Management

### Memory Types and Storage

```python
# Memory type detection
from kimi_proxy.features.mcp.detector import MCPDetector

detector = MCPDetector()
memory_type = detector.detect_memory_type(message_content)
# Returns: "frequent", "episodic", or "semantic"

# Store memory metrics
from kimi_proxy.features.mcp.storage import save_memory_metrics

await save_memory_metrics(session_id, {
    "type": memory_type,
    "tokens": token_count,
    "timestamp": datetime.now(),
    "content_hash": content_hash
})
```

### Memory Analysis

```python
# Analyze memory patterns
from kimi_proxy.features.mcp.analyzer import analyze_mcp_memory_in_messages

analysis = await analyze_mcp_memory_in_messages(messages)
print(f"Memory distribution: {analysis['memory_types']}")
print(f"Total memory tokens: {analysis['total_memory_tokens']}")
```

## MCP Integration Patterns

### Workflow Integration

```python
# Combine multiple MCP tools
async def debug_with_mcp():
    # 1. Use filesystem to read logs
    fs_client = get_mcp_client("fast_filesystem")
    logs = await fs_client.call("read_file", {
        "path": "/home/kidpixel/kimi-proxy/logs/proxy.log"
    })
    
    # 2. Use sequential thinking to analyze
    st_client = get_mcp_client("sequential_thinking")
    analysis = await st_client.call("sequentialthinking_tools", {
        "available_mcp_tools": ["filesystem", "json-query"],
        "thought": f"Analyzing logs: {logs[:500]}...",
        "next_thought_needed": True,
        "thought_number": 1,
        "total_thoughts": 3
    })
    
    # 3. Use task master to create debugging tasks
    tm_client = get_mcp_client("task_master")
    await tm_client.call("add_task", {
        "projectRoot": "/home/kidpixel/kimi-proxy",
        "prompt": "Fix streaming ReadError based on log analysis",
        "research": True
    })
```

### Error Handling

```python
# Robust MCP error handling
from kimi_proxy.features.mcp.client import MCPConnectionError, MCPClientError

try:
    result = await client.call("tool_name", params)
except MCPConnectionError:
    # Server disconnected, try restart
    await restart_mcp_server("task_master")
    result = await client.call("tool_name", params)
except MCPClientError as e:
    # Tool-specific error
    logger.error(f"MCP tool error: {e}")
    raise
```

## Troubleshooting MCP Issues

### Common Problems

**Server not responding:**
```bash
# Check if server is running
netstat -tlnp | grep -E ':(8002|8003|8004|8005)'

# Restart specific server
./scripts/start-mcp-servers.sh restart-task-master
```

**Workspace permissions:**
```python
# Validate workspace access
from kimi_proxy.features.mcp.client import validate_workspace_access

if not validate_workspace_access("/home/kidpixel/kimi-proxy"):
    raise ValueError("Workspace access denied")
```

**JSON-RPC errors:**
```bash
# Test MCP server directly
curl -X POST http://localhost:8002/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}'
```

## Performance Optimization

### Caching Strategies

```python
# Cache MCP responses
from functools import lru_cache

@lru_cache(maxsize=128)
async def cached_mcp_call(server_name: str, method: str, params_hash: str):
    client = get_mcp_client(server_name)
    return await client.call(method, params)
```

### Batch Operations

```python
# Batch file operations
async def batch_file_operations(operations):
    client = get_mcp_client("fast_filesystem")
    return await client.call("batch_file_operations", {
        "operations": operations,
        "stop_on_error": False
    })
```
