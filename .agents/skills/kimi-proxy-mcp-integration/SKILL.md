---
name: kimi-proxy-mcp-integration
description: Comprehensive MCP integration for Kimi Proxy Middleware MCP. Use when working on the MCP gateway, memory storage, Qdrant/compression clients, pruner servers, or the stdio bridge.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy MCP Integration

**TL;DR**: le stack MCP combine une gateway JSON-RPC (`/api/mcp-gateway/{server}/rpc`), un pont stdio (`scripts/mcp_bridge.py`), un stockage mémoire SQLite (`mcp_memory_entries`), Qdrant pour les vecteurs, et deux moteurs de pruning (`mcp_pruner`, `mcp_tool_pruning`). Les tables compaction/auto-memory ont été supprimées.

## Source of Truth

- `src/kimi_proxy/api/routes/mcp_gateway.py`
- `src/kimi_proxy/api/routes/mcp.py`
- `src/kimi_proxy/features/mcp/`
- `src/kimi_proxy/features/mcp_pruner/`
- `src/kimi_proxy/features/mcp_tool_pruning/`
- `src/kimi_proxy/features/observation_masking/`
- `scripts/mcp_bridge.py`
- `scripts/start-mcp-servers.sh`

## Gateway MCP

Endpoint :

```text
POST /api/mcp-gateway/{server_name}/rpc
```

Serveurs mappés :

| Nom logique | URL |
| :--- | :--- |
| `context-compression` | `http://127.0.0.1:8001` |
| `sequential-thinking` | `http://127.0.0.1:8003` |
| `fast-filesystem` | `http://127.0.0.1:8004` |
| `json-query` | `http://127.0.0.1:8005` |
| `pruner` | `http://127.0.0.1:8006` |

La gateway :

- forwarde le JSON-RPC brut ;
- applique un cache TTL de 30 s sur les lectures ;
- borne le cache à 512 entrées ;
- applique un circuit breaker par serveur ;
- tronque les réponses volumineuses via `MCPGatewayService.mask_jsonrpc_response`.

## Mémoire MCP

- Table SQLite : `mcp_memory_entries`.
- Types : `frequent`, `episodic`, `semantic`.
- `MemoryManager` : `store_memory`, `get_frequent_memories`, `find_similar_memories`, `get_memory_stats`, `cleanup_old_episodic_memories`, `detect_and_promote_frequent_patterns`.
- Qdrant reçoit les vecteurs sémantiques via `features/mcp/servers/qdrant.py`.
- La compression contextuelle passe par `features/mcp/servers/compression.py`.

Routes :

- `GET /api/memory/stats`
- `GET /api/memory/servers`
- `GET /api/memory/frequent`
- `GET /api/memory/similar/{session_id}`
- `POST /api/memory/similarity`
- `POST /api/memory/compress`
- `POST /api/memory/store?session_id=N`
- `POST /api/memory/cluster/{session_id}`
- `POST /api/memory/cleanup`
- `POST /api/memory/promote-patterns/{session_id}`

## Pruning

### `mcp_pruner` (serveur autonome, port 8006)

- Backends : `heuristic`, `local_rag`, `deepinfra`.
- Pipeline configurable via `KIMI_PRUNING_BACKEND` ou `[mcp_pruner].backend`.
- Outils MCP : `prune_text`, `recover_text`, `health`.
- Fail-open vers le backend heuristique.

### `mcp_tool_pruning`

- Élague les réponses `tools/call` volumineuses.
- Flag `[mcp_tool_pruning].enabled` (désactivé par défaut).
- Fallback tête/queue et métriques metadata-only.

### Observation masking

- `features/observation_masking/schema1.py`.
- Flag `[observation_masking.schema1].enabled` (désactivé par défaut).
- Remplace les vieux tool results par un placeholder court.

## Bridge stdio

`scripts/mcp_bridge.py` relaie les serveurs stdio vers les IDE :

- `filesystem-agent`
- `ripgrep-agent`
- `shrimp-task-manager`

Il filtre stdout pour ne laisser passer que le JSON-RPC, supprime les notifications sans `id`, et shim `roots/list` pour Shrimp.

## Erreurs

- `MCPGatewayUpstreamError` : `unknown_server`, `timeout`, `connect_error`, `invalid_json`, `http_error`.
- `MCPClientError`, `MCPConnectionError`, `MCPTimeoutError` dans `features/mcp/base/rpc.py`.

## Vérification

```bash
curl -s -X POST http://localhost:8000/api/mcp-gateway/pruner/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

PYTHONPATH=src venv/bin/python -m pytest tests/unit/features/test_mcp_gateway.py -q
PYTHONPATH=src venv/bin/python -m pytest tests/unit/test_mcp_bridge.py -q
PYTHONPATH=src venv/bin/python -m pytest tests/unit/features/test_mcp_pruner_server.py -q
```

## ❌ Ne pas réintroduire

- Tables `compaction_history`, `mcp_compression_results`, `mcp_routing_decisions`, `memory_metrics`, `memory_segments`.
- `features/compaction/`, `features/compression/`, `features/mcp/auto_memory.py`, `features/mcp/storage.py`.
- Routes `/api/sessions/*`, `/api/compaction/*`, `/api/compress/*`.
- Broadcast WebSocket.

## Golden Rule

**Le contrat MCP est JSON-RPC 2.0, pas une collection de routes REST inventées.** Toute nouvelle capacité MCP doit passer par la gateway ou le bridge, avec un test de handshake et un fallback explicite.
