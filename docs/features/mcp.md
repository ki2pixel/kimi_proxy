# MCP Module — Serveurs, UI et Gateway

## TL;DR
Le module frontend `static/js/modules/mcp.js` pilote l’affichage MCP en deux groupes visuels (Phase 3 et Phase 4). Côté backend actuel, `GET /api/memory/all-servers` repose encore sur **2 statuts réels** (`qdrant`, `context-compression`), tandis que le gateway HTTP route **5 serveurs nommés**.

## Problème
La documentation mélange facilement trois plans différents: statut backend réel, classification frontend et routage gateway. Résultat: des chiffres globaux (serveurs, outils) peuvent sembler cohérents, mais ne correspondent pas strictement à ce qui est calculé en runtime.

## Vue d’ensemble technique

### 1) Frontend MCP (UI)
Le module `static/js/modules/mcp.js`:
- charge `GET /api/memory/all-servers`, fallback `GET /api/memory/servers`;
- maintient `mcpState.phase3Servers` et `mcpState.phase4Servers`;
- rend un panneau status + stats + mémoires fréquentes;
- applique un refresh périodique toutes les 30 secondes.

### 2) Backend statut MCP
Dans `src/kimi_proxy/features/mcp/client.py`, `get_all_server_statuses()` retourne actuellement:
- `qdrant.check_status()`
- `compression.check_status()`

La segmentation Phase 3/Phase 4 de la réponse API existe, mais la source de statuts reste aujourd’hui centrée sur ces deux clients spécialisés.

### 3) Gateway MCP HTTP
`POST /api/mcp-gateway/{server_name}/rpc` forwarde du JSON-RPC brut vers:
- `context-compression`
- `sequential-thinking`
- `fast-filesystem`
- `json-query`
- `pruner`

## Ce qui est vrai en runtime

### ❌ Interprétation naïve
- Le dashboard affiche Phase 3 + Phase 4, donc tous les statuts proviennent forcément de 6 serveurs backend monitorés de la même façon.

### ✅ État actuel
- Le frontend est structuré pour Phase 3 + Phase 4.
- Le backend statut (`get_all_server_statuses`) remonte aujourd’hui 2 serveurs principaux.
- Le gateway peut forwarder 5 serveurs nommés, dont `pruner`.

## Endpoints MCP utilisés

### Statut et métriques
- `GET /api/memory/servers`
- `GET /api/memory/all-servers`
- `GET /api/memory/stats/advanced`
- `GET /api/memory/frequent`

### Opérations mémoire
- `POST /api/memory/similarity`
- `POST /api/memory/compress`
- `POST /api/memory/store`
- `POST /api/memory/cluster/{session_id}`
- `GET /api/memory/similar/{session_id}`
- `POST /api/memory/cleanup`
- `POST /api/memory/promote-patterns/{session_id}`

### Gateway
- `POST /api/mcp-gateway/{server_name}/rpc`

## Trade-offs
| Choix | Avantage | Limite |
|---|---|---|
| UI prête pour Phase 3+4 complète | Évolutive côté dashboard | Peut suggérer une parité backend immédiate |
| Statut backend focalisé sur clients spécialisés | Simplicité opérationnelle | Couverture partielle des serveurs IDE/outils |
| Gateway par mapping explicite | Contrôle fin des serveurs routables | Nécessite maintien du mapping au fil des ajouts |

## Golden Rule
**Séparer explicitement dans la doc: visualisation frontend, collecte de statuts backend et capacité de routage gateway.**

---
*Dernière mise à jour: 2026-02-26*  
*Conforme documentation/SKILL.md: TL;DR, problem-first, bloc ❌/✅, trade-offs, Golden Rule.*
