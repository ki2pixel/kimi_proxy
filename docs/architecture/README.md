# Architecture du middleware

**TL;DR** : Kimi Proxy est un middleware session-less. Le client fournit la cible et sa clé provider ; le proxy applique les features MCP, puis relaie la requête en HTTP/SSE.

## Les cinq couches

```text
API (FastAPI)
  ↓
Services (streaming SSE, callbacks)
  ↓
Features (MCP, mémoire, masking, pruning, log watcher)
  ↓
Proxy (HTTPX, passthrough, réparation tool_calls)
  ↓
Core (SQLite, Tiktoken, dataclasses, constantes)
```

Chaque couche ne dépend que des couches inférieures. Core n'a aucune dépendance externe et ne fait aucun appel réseau.

## Flux réel

```text
Client OpenAI-compatible
  │  POST /v1/chat/completions
  │  X-Target-Base-URL + Authorization
  ▼
API (mcp_passthrough)
  ▼
Features (tool fixing, observation masking, context pruning)
  ▼
Proxy (validation SSRF, HTTPX, SSE)
  ▼
Provider upstream
```

La route historique `POST /chat/completions`, le pipeline sessions/métriques, la compaction, la compression et les WebSockets ont été retirés. Le seul endpoint de chat est `/v1/chat/completions`.

## Modules clés

| Couche | Module | Rôle |
| :--- | :--- | :--- |
| API | `api/routes/mcp_passthrough.py` | Entrée OpenAI-compatible |
| API | `api/routes/mcp_gateway.py` | Gateway JSON-RPC MCP |
| API | `api/routes/mcp.py` | Mémoire MCP |
| API | `api/routes/sanitizer.py` | Lecture des contenus masqués |
| Features | `features/mcp/` | Client Qdrant/compression, mémoire SQLite |
| Features | `features/mcp_tool_pruning/` | Élagage des réponses tools/call |
| Features | `features/mcp_pruner/` | Serveur de pruning autonome |
| Features | `features/observation_masking/` | Masquage des vieux tool results |
| Features | `features/log_watcher/` | Lecture des logs Continue/Kimi |
| Proxy | `proxy/passthrough.py` | Validation cible, headers, forward |
| Proxy | `proxy/stream.py` | Relay SSE pur |
| Proxy | `proxy/tool_utils.py` | Réparation des tool_calls |
| Core | `core/database.py` | SQLite minimal |
| Core | `core/tokens.py` | Comptage Tiktoken |

## Invariants

1. Core ne dépend d'aucun package externe.
2. Aucune I/O bloquante ajoutée dans un handler async : la résolution DNS du passthrough est asynchrone.
3. Le streaming utilise exclusivement `StreamingResponse` (SSE).
4. Les routes `/api/*` sont protégées par `KIMI_ADMIN_KEY`.
5. `/v1/chat/completions` lit la clé admin dans `X-Admin-Key`, jamais dans `Authorization`.
6. Le schéma SQLite est minimal : `masked_content` et `mcp_memory_entries`.

## Fichiers historiques

Les documents `modular-architecture-v2.md`, `docs/development/migration-v2.md` et les guides de features supprimées décrivent l'ancienne architecture. Ils sont conservés comme historique et ne doivent pas servir de référence pour le runtime actuel.
