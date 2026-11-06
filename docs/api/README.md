# API Kimi Proxy Middleware MCP

**TL;DR** : le middleware expose une surface OpenAI-compatible minimale (`/models`, `/v1/chat/completions`) et une gateway JSON-RPC MCP (`/api/mcp-gateway/{server}/rpc`). Les routes sessions, compaction, compression et WebSocket ont été retirées.

## Surface exposée

| Méthode | Chemin | Rôle |
| :--- | :--- | :--- |
| `GET` | `/` | Métadonnées du service |
| `GET` | `/health` | Health minimal public |
| `GET` | `/models` | Liste OpenAI-compatible (`object: "list"`) |
| `GET` | `/api/models` | Liste interne des modèles |
| `POST` | `/v1/chat/completions` | Passthrough session-less avec `X-Target-Base-URL` |
| `POST` | `/api/mcp-gateway/{server_name}/rpc` | Forward JSON-RPC 2.0 vers un serveur MCP local |

Routes mémoire conservées :

| Méthode | Chemin |
| :--- | :--- |
| `GET` | `/api/memory/stats` |
| `GET` | `/api/memory/servers` |
| `GET` | `/api/memory/frequent` |
| `GET` | `/api/memory/similar/{session_id}` |
| `POST` | `/api/memory/similarity` |
| `POST` | `/api/memory/compress` |
| `POST` | `/api/memory/store?session_id=N` |
| `POST` | `/api/memory/cluster/{session_id}` |
| `POST` | `/api/memory/cleanup` |
| `POST` | `/api/memory/promote-patterns/{session_id}` |

Routes sanitizer en lecture :

| Méthode | Chemin |
| :--- | :--- |
| `GET` | `/api/mask` |
| `GET` | `/api/mask/{content_hash}` |
| `GET` | `/api/sanitizer/stats` |

## Passthrough `/v1/chat/completions`

Le client envoie la cible et sa clé provider :

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Target-Base-URL: https://api.openai.com/v1" \
  -H "Authorization: Bearer $PROVIDER_API_KEY" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
```

Le proxy applique dans l'ordre :

1. Réparation des `tool_calls` et normalisation des arguments JSON.
2. Observation masking (flag `observation_masking.schema1.enabled`).
3. Context pruning via MCP Pruner (flag `context_pruning.enabled`).

Le streaming utilise exclusivement SSE (`StreamingResponse`). Aucun endpoint WebSocket n'est exposé.

## Authentification

- `KIMI_ADMIN_KEY` protège les routes `/api/*`.
- Si `KIMI_ADMIN_KEY` est défini, `/v1/chat/completions` attend la clé admin dans `X-Admin-Key`. Le header `Authorization` reste réservé à la clé provider.
- En développement, l'absence de `KIMI_ADMIN_KEY` laisse les routes ouvertes (fail-open local).

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Admin-Key: $KIMI_ADMIN_KEY" \
  -H "Authorization: Bearer $PROVIDER_API_KEY" \
  -H "X-Target-Base-URL: https://api.openai.com/v1" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[]}'
```

## Routes retirées

Les routes suivantes ont été supprimées et renvoient `404` :

- `POST /chat/completions` (legacy, inerte sans `[providers]`).
- `GET` et `POST /api/sessions/*`.
- `POST /api/compaction/*`.
- `POST /api/compress/*`.
- `GET /api/providers`, `/api/export/*`, `/api/cline/*`.
- `GET /api/admin/health`, `/api/rate-limit`.
- `GET /api/memory/stats/advanced`, `/api/memory/all-servers`.
- `WS /ws`.

## Erreurs

- `400` : JSON invalide ou cible refusée par la validation SSRF.
- `401` : clé admin absente ou invalide (`KIMI_ADMIN_KEY` défini).
- `404` : route retirée ou serveur MCP inconnu dans la gateway.
- `502` : erreur de connexion ou timeout vers le provider ou le serveur MCP.
- `503` : `X-Target-Base-URL` absent.
