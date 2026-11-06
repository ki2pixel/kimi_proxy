---
name: kimi-proxy-config-manager
description: Expert configuration management for Kimi Proxy Middleware MCP. Use when editing config.toml, feature flags, MCP gateway settings, or environment variables.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Configuration Manager

**TL;DR**: `config.toml` ne contient plus de providers ni de modèles. Il pilote uniquement les features MCP (masking, pruning, mémoire, gateway) et la persistance. Le client fournit `X-Target-Base-URL` et sa clé dans `Authorization`.

## Source of Truth

- `config.toml` : flags et paramètres MCP.
- `src/kimi_proxy/config/loader.py` : lecture TOML, expansion `${VAR}`, getters typés.
- `src/kimi_proxy/proxy/passthrough.py` : résolution de la cible et validation SSRF.
- `src/kimi_proxy/api/routes/mcp_gateway.py` : mapping des serveurs MCP locaux.

## Architecture Rules

- `config/` ne dépend pas de `features/*`.
- Les secrets restent en variables d'environnement ou en valeurs `${VAR}`.
- Aucun provider ni modèle n'est configuré dans le fichier : l'architecture est session-less.
- Toute nouvelle clé TOML doit avoir un getter et un test dans `config/loader.py`.

## Sections réellement lues

| Section | Getter | Usage |
| :--- | :--- | :--- |
| `[observation_masking.schema1]` | `get_observation_masking_schema1_config` | Masquage des vieux tool results |
| `[log_watcher]` | `get_log_watcher_config` | Lecture des logs Continue/Kimi |
| `[database]` | `get_database_config` | Persistance SQLite |
| `[sanitizer]` | `get_sanitizer_config` | Affichage des seuils |
| `[context_pruning]` | `get_context_pruning_config` | Élagage via MCP Pruner |
| `[mcp_tool_pruning]` | `get_mcp_tool_pruning_config` | Élagage des réponses tools/call |
| `[mcp_pruner]` | `get_mcp_pruner_backend_config` | Backend du serveur pruner |
| `[mcp.gateway]` | `get_mcp_gateway_config` | Circuit breaker du gateway |
| `[mcp.qdrant]` | `MCPClientConfig.from_toml` | URL, clé, collection, timeout |
| `[mcp.compression]` | `MCPClientConfig.from_toml` | URL, clé, timeout |
| `[mcp.retry]` | `MCPClientConfig.from_toml` | Retries RPC |

## Exemple de configuration

```toml
[observation_masking.schema1]
enabled = false
window_turns = 8
keep_errors = true
keep_last_k_per_tool = 0

[database]
persist_sessions = false

[context_pruning]
enabled = false
min_chars_to_prune = 2000
call_timeout_ms = 1500

[mcp_tool_pruning]
enabled = false

[mcp_pruner]
backend = "heuristic,local_rag"
cache_ttl_s = 30
cache_max_entries = 256

[mcp.gateway]
cb_enabled = true
cb_max_failures = 5
cb_similarity_threshold = 0.85

[mcp.qdrant]
url = "https://..."
api_key = "${QDRANT_API_KEY}"
collection = "kimi_proxy_memory"
search_timeout_ms = 50

[mcp.compression]
url = "http://localhost:8001"
api_key = ""
compression_timeout_ms = 5000
```

## Variables d'environnement

| Variable | Effet |
| :--- | :--- |
| `KIMI_ADMIN_KEY` | Protège `/api/*` ; requis en production |
| `KIMI_ENV` | `development` ou `production` (CORS, SSRF, fail-fast admin) |
| `KIMI_PERSIST_SESSIONS` | Force `true`/`false` pour SQLite |
| `KIMI_PRUNING_BACKEND` | Priorité sur `[mcp_pruner].backend` |
| `DEEPINFRA_API_KEY` | Active le backend DeepInfra |
| `QDRANT_API_KEY` | Clé Qdrant Cloud |
| `LOG_WATCHER_ENABLED` | Force l'activation du log watcher |
| `KIMI_MCP_TOOL_PRUNING_ENABLED` | Priorité sur `[mcp_tool_pruning].enabled` |
| `KIMI_MCP_TOOL_PRUNING_EXCLUDED_DIRS` | Répertoires exclus du pruning |

## Diagnostics

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/models
curl -s http://localhost:8000/api/models
curl -s http://localhost:8000/api/memory/stats
curl -s -X POST http://localhost:8000/api/mcp-gateway/pruner/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

## Erreurs fréquentes

- `503 Cible manquante` : `X-Target-Base-URL` absent.
- `401` sur `/v1/chat/completions` : `X-Admin-Key` absent alors que `KIMI_ADMIN_KEY` est défini.
- `502` gateway : serveur MCP arrêté ou port incorrect.
- `ConfigurationError` au démarrage en production : `KIMI_ADMIN_KEY` manquant.

## Golden Rule

**Si une clé n'est lue par aucun getter de `config/loader.py`, elle ne doit pas être documentée comme active.** Le fichier de configuration décrit le middleware, pas un provider.
