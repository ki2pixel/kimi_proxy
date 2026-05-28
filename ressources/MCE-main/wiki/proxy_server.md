# Proxy Server Orchestrator
Parent: [[index]]
Tags: #orchestrator
---

## Summary
The `ProxyServer` handles FastAPI routing, Lifespan initialization of modules, JSON-RPC schema normalization, and drives the pipeline orchestrations described in [[mental_model]].

## Code References
*   [proxy_server.py](file:///Users/k3x/Developer/MCE/mce-core/core/proxy_server.py) — Implements pipeline steps and HTTP routes.
*   [context_manager.py](file:///Users/k3x/Developer/MCE/mce-core/core/context_manager.py) — Session statistics tracking.

## Core Operations

### Lifespan Event Handlers
On startup, uvicorn triggers the lifespan handler:
1.  **McpClient Initialization**: Launches the client communicating with upstream servers.
2.  **Module Initializations**: Spawns the intelligence layers, including `SkillLoader`, `PermissionGate`, `DriftSentinel`, `TimeMachine`, and `MemVault`.
3.  **TUI Dashboard Spawn**: If configured, launches the TUI dashboard interface in a separate daemon thread.
4.  **CLAUDE.md Auto-Save Registration**: Registers memory dump tasks upon shutdown to write logs directly back to the project root directory.

### Pipeline Orchestration
- Normalizes dual-mode JSON-RPC requests (`tools/call` vs direct methods).
- Coordinates policy checks and HitL prompt decisions.
- Invokes post-execution caching and token pruners.
- Dynamically coordinates error state checks with the [[circuit_breaker]] loop prevention component.
