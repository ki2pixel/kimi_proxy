# Lazy Registrar & Meta-Tools
Parent: [[index]]
Tags: #orchestrator, #optimization
---

## Summary
The `LazyRegistrar` manages tool schemas dynamically. Instead of dumping all schemas to the agent system prompt upfront (causing a "token tax"), schemas are grouped into domains (e.g. `@filesystem`, `@database`) and injected/unloaded on-demand using meta-tools.

## Code References
*   [lazy_registrar.py](file:///Users/k3x/Developer/MCE/mce-core/engine/lazy_registrar.py) — Dynamic tool registration and semantic search.
*   [vector_store.py](file:///Users/k3x/Developer/MCE/mce-core/models/vector_store.py) — In-memory numpy vector store.
*   [embeddings.py](file:///Users/k3x/Developer/MCE/mce-core/models/embeddings.py) — Lazy embedding model loader.

## Meta-Tools API

### 1. `discover_capabilities`
- **Goal**: Activates a specific domain group and registers its tools.
- **Parameters**: `domain` (string, e.g. `'filesystem'`).
- **Flow**: Returns the dynamic list of matching tool schemas and registers them in uvicorn's active schemas.

### 2. `release_capabilities`
- **Goal**: Unloads a domain group and deletes its tool schemas from active memory.
- **Parameters**: `domain` (string).
- **Benefit**: Frees up context space when the agent is done with a domain.

### 3. `search_tools`
- **Goal**: Find and register tool schemas semantically using natural language queries.
- **Parameters**: `query` (string), `top_k` (integer).
- **Embedding Search**:
  - Encodes tool descriptions and the agent query using `EmbeddingModel`.
  - Performs similarity matching using the pre-normalized `VectorStore`.
  - Dynamically registers the matching schemas and returns their definitions.
