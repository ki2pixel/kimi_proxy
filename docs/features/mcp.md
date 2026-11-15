# MCP Module — Statuts, Gateway et Mémoire

## TL;DR
Kimi Proxy est un middleware headless. Il n'y a plus de frontend `static/js/modules/mcp.js` ni de routes `/api/memory/all-servers` ou `/api/memory/stats/advanced`. La gateway route cinq serveurs MCP locaux, et les routes mémoire exposent uniquement les opérations réellement implémentées.

## Le problème
La documentation mélangeait trois plans différents : l'ancien dashboard, les statuts MCP réellement collectés et le routage de la gateway. Résultat : des routes et des modules supprimés continuaient d'apparaître comme disponibles.

## Ce qui existe réellement

### API headless
Les routes MCP sont servies par FastAPI, sans dashboard ni WebSocket. Toutes les routes `/api/*` sont protégées par `KIMI_ADMIN_KEY` lorsque la variable est définie. Le client peut fournir la clé via `X-Admin-Key` ou `Authorization: Bearer`.

### Statuts MCP
`MCPExternalClient.get_all_server_statuses()` interroge deux clients spécialisés :
- Qdrant MCP
- Context Compression MCP

La gateway peut néanmoins router cinq serveurs nommés, dont trois ne sont pas couverts par cette collecte de statuts.

### Gateway MCP
`POST /api/mcp-gateway/{server_name}/rpc` forwarde une requête JSON-RPC 2.0 vers :

| Serveur logique | URL locale |
|---|---|
| `context-compression` | `http://127.0.0.1:8001` |
| `sequential-thinking` | `http://127.0.0.1:8003` |
| `fast-filesystem` | `http://127.0.0.1:8004` |
| `json-query` | `http://127.0.0.1:8005` |
| `pruner` | `http://127.0.0.1:8006` |

Un corps JSON invalide retourne une erreur JSON-RPC `-32700` avec le statut HTTP 400. Un serveur inconnu retourne `-32001` avec le statut 404.

### Résolution des chemins `fast-filesystem`
Le serveur `fast-filesystem` est un daemon HTTP partagé, écoute sur `127.0.0.1:8004` et utilise `MCP_ALLOWED_ROOT=/home/kidpixel` (la racine `/` est refusée au démarrage).

- **Client HTTP direct** (Cline, Windsurf, Continue) : chemins absolus obligatoires. Un chemin relatif retourne `-32602 RELATIVE_PATH_UNSUPPORTED`.
- **OpenCode** : `fast-filesystem` passe par `scripts/mcp_bridge.py fast-filesystem`, qui injecte `params._meta["ai.kimi-proxy/workspaceRoot"]` (cwd du workspace). Un chemin relatif est alors résolu sous ce workspace et ne peut pas en sortir (`RELATIVE_PATH_ESCAPES_WORKSPACE`).
- Un chemin absolu explicite reste possible sous `/home/kidpixel` (`OPTION A+`) pour les accès inter-projets intentionnels.
- `_meta` est une base de résolution, **pas** une autorisation : la frontière reste `MCP_ALLOWED_ROOT`.
- Les refus de sécurité upstream (HTTP 403, `-32000 PATH_OUTSIDE_ALLOWED_ROOT`) sont forwardés par la gateway sous forme de réponse JSON-RPC ; la gateway elle-même répond HTTP 200 avec la charge d'erreur.

### Mémoire
La mémoire SQLite est réduite aux tables `mcp_memory_entries` et `masked_content`. Les accès SQLite de `MemoryManager` sont exécutés hors de la boucle asyncio via `run_db_in_thread`.

## Endpoints réellement exposés

### Mémoire
- `GET /api/memory/stats`
- `GET /api/memory/servers`
- `GET /api/memory/frequent`
- `POST /api/memory/similarity`
- `POST /api/memory/compress`
- `POST /api/memory/store`
- `POST /api/memory/cluster/{session_id}`
- `GET /api/memory/similar/{session_id}`
- `POST /api/memory/cleanup`
- `POST /api/memory/promote-patterns/{session_id}`

### Sanitizer
- `GET /api/mask/{content_hash}`
- `GET /api/mask`
- `GET /api/sanitizer/stats`

### Gateway
- `POST /api/mcp-gateway/{server_name}/rpc`

## ❌ Ancienne interprétation
- Le module `static/js/modules/mcp.js` pilote l'affichage MCP.
- `GET /api/memory/all-servers` et `GET /api/memory/stats/advanced` sont disponibles.
- Tous les serveurs routés par la gateway remontent aussi un statut.

## ✅ État actuel
- Aucun frontend MCP n'est embarqué ; le middleware est consommé par les IDE et les clients HTTP.
- Les routes mémoire sont limitées à la liste ci-dessus.
- La gateway route cinq serveurs, tandis que la collecte de statuts reste centrée sur Qdrant et Context Compression.

## Trade-offs

| Choix | Avantage | Limite |
|---|---|---|
| Middleware headless | Surface d'attaque réduite et déploiement simple | Pas de visualisation intégrée |
| Statuts focalisés sur deux clients | Code de monitoring simple | Couverture partielle des serveurs routés |
| Mapping gateway explicite | Contrôle fin des cibles locales | Nécessite une mise à jour à chaque nouveau serveur |
| Erreurs JSON-RPC normalisées | Contrat stable pour les clients | Les messages changent, pas les codes |

## Golden Rule
**La gateway peut router plus de serveurs que le monitoring n'en expose. Documenter ces deux périmètres séparément.**

---
*Dernière mise à jour : 2026-11-06*
*Conforme à `.agents/skills/documentation/SKILL.md` : TL;DR, problem-first, blocs ❌/✅, trade-offs, Golden Rule.*
