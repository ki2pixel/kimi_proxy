# Mental Model & General Concepts
Parent: [[index]]
Tags: #documentation, #orchestrator
---

## Summary
The Model Context Engine (MCE) acts as a smart, transparent caching CDN and security gate between a client AI agent (the master intelligence) and upstream Model Context Protocol (MCP) tool servers.

## Code References
*   [main.py](file:///Users/k3x/Developer/MCE/mce-core/main.py) — Application entrypoint, configuration loader, and server initialization.
*   [config.yaml](file:///Users/k3x/Developer/MCE/mce-core/config.yaml) — Declarative YAML configuration containing token budgets, security settings, cache TTL, and active profiles.

## Architecture Diagram
Instead of calling tool servers directly, the agent issues JSON-RPC calls which are intercepted by the MCE Proxy Server.

```
┌──────────┐     JSON-RPC     ┌──────────┐     JSON-RPC     ┌──────────────┐
│ AI Agent │ ───────────────→ │   MCE    │ ───────────────→ │  MCP Server  │
│          │ ←── minified ─── │  Proxy   │ ←──── raw ────── │  (Tool)      │
└──────────┘                  └──────────┘                  └──────────────┘
                                   │
                           ┌───────┴───────┐
                           │ Squeeze Engine │
                           │  L1: Pruner   │  ← deterministic, ~0ms
                           │  L2: Semantic │  ← CPU embeddings
                           │  L3: Synth.   │  ← local LLM (optional)
                           └───────────────┘
```

## The Request Lifecycle
Every incoming request processed in [[proxy_server]] goes through this exact pipeline:

1.  **Normalization**: MCP dual-mode conversion (supports method-as-tool-name and standard `tools/call`).
2.  **Meta-Tool Handling**: Routes matching requests to `discover_capabilities`, `release_capabilities`, or `search_tools` in [[lazy_registrar]].
3.  **Semantic Cache Check**: If cache hit is found, immediately returns the result (see [[squeezing]]).
4.  **Security Gate Check (Pre-flight)**: Queries `PermissionGate` and `PolicyEngine` (see [[guardian]]).
5.  **Upstream Execution**: Forwards JSON-RPC to the actual tool server via `McpClient`.
6.  **Loop Prevention (CircuitBreaker)**: Checks if the execution resulted in an error (JSON-RPC or logical `isError`) and records in [[circuit_breaker]].
7.  **Security Content Check (Post-flight)**: Validates response payload against policy rules.
8.  **Token Budget Evaluation**: Checks if response size exceeds limits (see [[token_economist]]).
9.  **Pruning & Compression**: Compresses payload using the 3-layer [[squeezing]] pipeline.
10. **State Monitoring**: Runs post-execution constraint validations in `DriftSentinel`.
11. **Caching**: Writes squeezed payload to cache. If a state mutating command executed successfully, clears the cache to ensure consistency.
12. **Intelligence Logging**: Saves tool call history and updates context stats (see [[memvault]] and [[cli]]).
