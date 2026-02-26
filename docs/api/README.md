# API Layer — Routes et Endpoints

## TL;DR
La couche API expose aujourd’hui **58 routes HTTP effectives** pour **56 couples méthode+chemin uniques**. Le point d’entrée central reste `POST /chat/completions`, avec une compatibilité OpenAI minimale via `GET /models`.

## Problème
Le code source contient des doublons de décorateurs et des routes historiques. Sans inventaire runtime FastAPI, la documentation diverge rapidement des chemins réellement exposés.

## Architecture 5 couches
```
API (FastAPI) ← Services (WebSocket) ← Features (MCP) ← Proxy (HTTPX) ← Core (SQLite)
```

## Inventaire vérifié (runtime)

### Sessions
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/active`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/activate`
- `GET /api/sessions/auto-status`
- `POST /api/sessions/toggle-auto`
- `DELETE /api/sessions` (bulk)
- `POST /api/sessions/vacuum`
- `GET /api/sessions/diagnostic`

### Providers et modèles
- `GET /api/providers`
- `GET /api/models`
- `GET /api/models/all`
- `GET /models` (format OpenAI-compatible)

### Proxy, santé, monitoring
- `POST /chat/completions`
- `GET /health`
- `GET /api/rate-limit`
- `WS /ws`

### Exports et sanitizer
- `GET /api/export/csv`
- `GET /api/export/json`
- `GET /api/mask/{content_hash}`
- `GET /api/mask`
- `GET /api/sanitizer/stats`
- `POST /api/sanitizer/toggle`

### Cline
- `GET /api/cline/status`
- `GET /api/cline/usage`
- `POST /api/cline/import`

### Mémoire MCP
- `GET /api/sessions/{session_id}/memory`
- `GET /api/memory/stats`
- `GET /api/memory/servers`
- `GET /api/memory/all-servers`
- `POST /api/memory/similarity`
- `POST /api/memory/compress`
- `POST /api/memory/store`
- `GET /api/memory/frequent`
- `POST /api/memory/cluster/{session_id}`
- `GET /api/memory/similar/{session_id}`
- `GET /api/memory/stats/advanced`
- `POST /api/memory/cleanup`
- `POST /api/memory/promote-patterns/{session_id}`

### Compaction et compression
- `POST /api/compaction/{session_id}`
- `GET /api/compaction/stats`
- `GET /api/compaction/{session_id}/stats`
- `GET /api/compaction/{session_id}/history`
- `GET /api/compaction/{session_id}/history-chart`
- `GET /api/compaction/{session_id}/preview`
- `POST /api/compaction/{session_id}/reserved`
- `POST /api/compaction/{session_id}/simulate`
- `POST /api/compaction/{session_id}/toggle-auto`
- `GET /api/compaction/{session_id}/auto-status`
- `GET /api/compaction/config/ui`
- `POST /api/compress/{session_id}`
- `GET /api/compress/stats`
- `GET /api/compress/{session_id}/stats`

### MCP Gateway
- `POST /api/mcp-gateway/{server_name}/rpc`
- Serveurs supportés côté proxy: `context-compression`, `sequential-thinking`, `fast-filesystem`, `json-query`, `pruner`

## Corrections de parité appliquées

### ❌ Avant
- `POST /api/compaction/{session_id}/reserved-tokens`
- `POST /api/compaction/{session_id}/auto-toggle`
- `GET /api/compaction/ui-config`
- `DELETE /api/sessions/{id}`

### ✅ Maintenant
- `POST /api/compaction/{session_id}/reserved`
- `POST /api/compaction/{session_id}/toggle-auto`
- `GET /api/compaction/config/ui`
- `DELETE /api/sessions`

## Notes de traçabilité
- `sessions.py` contient deux doublons de décorateurs (`/auto-status`, `/toggle-auto`).
- `memory.py` existe dans `api/routes`, mais son router n’est pas monté dans `api/router.py`.
- Les métriques de cette page proviennent de l’application FastAPI montée, pas uniquement des décorateurs source.

## Trade-offs
| Approche | Avantage | Limite |
|---|---|---|
| Compter les décorateurs | Rapide | Sur-estime la surface réelle |
| Compter les routes montées | Fidèle runtime | Demande un contrôle applicatif |
| Choix actuel | Documentation exacte à l’exécution | Doit être relancée après refactor routeur |

## Golden Rule
**Documenter à partir des routes montées, puis signaler explicitement les doublons et routes non montées.**

## Métriques API
- 60 décorateurs HTTP détectés dans les fichiers de routes
- 58 routes HTTP effectives
- 56 couples méthode+chemin uniques
- 13 fichiers avec décorateurs actifs (`api/routes` contient 15 fichiers avec `__init__.py` et `websocket.py`)

---
*Dernière mise à jour: 2026-02-26*  
*Conforme documentation/SKILL.md: TL;DR, problem-first, blocs ❌/✅, trade-offs, Golden Rule.*
