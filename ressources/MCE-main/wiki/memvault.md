# MemVault SQLite DB Memory
Parent: [[index]]
Tags: #state
---

## Summary
`MemVault` is an in-memory or SQLite database tracking session operations, learning logs, decisions, and constraints. During shutdown, it exports accumulated memories directly to the project's root `CLAUDE.md`.

## Code References
*   [memvault.py](file:///Users/k3x/Developer/MCE/mce-core/engine/intelligence/memvault.py) — Ingests and formats session memories.
*   [memory_store.py](file:///Users/k3x/Developer/MCE/mce-core/models/memory_store.py) — SQL interface for reading/writing logs.

## Ingestion & Memory Classification
As the agent runs tools, MCE captures memories and classifies them:
1.  **Decisions**: Choices made by the agent (e.g. opting to run tests with a specific flag).
2.  **Dead Ends**: Troubleshooting paths that failed.
3.  **Constraints**: Project-level rules discovered.

## Auto-Exporting to CLAUDE.md
During uvicorn server shutdown, `MemVault` compiles these memories and appends them to the root `CLAUDE.md` of the workspace. This ensures the master agent retains context across sessions (avoiding agent amnesia).
