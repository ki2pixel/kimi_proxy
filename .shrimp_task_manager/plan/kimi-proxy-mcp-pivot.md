# Brief: Pivot MCP-First de Kimi Proxy

## Contexte
L'utilisateur a migré son usage quotidien vers **Cline**, qui gère automatiquement la fenêtre de contexte avec ses modèles. Le frontend du Dashboard (UI, WebSocket visuel, sessions visuelles, graphiques Chart.js, etc.) est désormais **obsolète pour son usage**.

Son flux de travail actuel passe exclusivement par `scripts/start-mcp-servers.sh` pour orchestrer les serveurs MCP (Shrimp Task Manager, Sequential Thinking, Fast Filesystem, JSON Query, Redis, Postgres, etc.).

## Objectif
**Recentrer le cœur de Kimi Proxy autour de ses features MCP**, en allégeant ou dépréciant le frontend et ses dépendances visuelles, **sans casser** les capacités MCP existantes ni l'architecture en 5 couches.

## Architecture Actuelle (5 couches)
```
API (FastAPI) ← Services (WebSocket) ← Features (MCP) ← Proxy (HTTPX) ← Core (SQLite)
```

## Composants Frontend à Déprécier
- `static/index.html` - Page d'accueil Dashboard
- `static/memory-section.html` - Section mémoire visuelle
- `static/js/modules/ui.js` - Interface utilisateur (38KB)
- `static/js/modules/charts.js` - Graphiques Chart.js (15KB)
- `static/js/modules/similarity-chart.js` - Graphiques similarité (14KB)
- `static/js/modules/sessions.js` - Gestion sessions visuelle (22KB)
- `static/js/modules/modals.js` - Modals UI (57KB)
- `static/js/modules/accessibility/` - Accessibilité UI
- `static/js/modules/websocket.js` - Client WebSocket dashboard
- `static/css/` - Stylesheets
- Route `/` dans `main.py` (HTMLResponse)
- Route `/favicon.ico`
- `app.mount("/static", ...)`

## Composants MCP/Core à Conserver ABSOLUMENT
- `scripts/start-mcp-servers.sh` - Point d'entrée principal MCP
- Toutes les routes `/api/*` et `/api/mcp-gateway/*`
- Features MCP : log_watcher, observation_masking, mcp_tool_pruning, context_compaction, auto_memory
- Services : websocket_manager (broadcast générique, pas uniquement UI)
- Proxy : routing, streaming, client HTTPX
- Core : database, models, constants, auto_session
- Configuration : `config.toml`, loader
- Base SQLite : tables MCP (memory, routing, compression, compaction)

## Point Critique : WebSocket Manager
Le `ConnectionManager` est utilise par **le backend** pour broadcaster des evenements (token updates, sessions, compaction, compression, memory). Il est **independant du frontend** et doit etre conserve. Le endpoint `/ws` peut rester disponible pour tout client (Cline, scripts) voulant s'y connecter.

## Dependences Frontend a Alleger
- Chart.js (CDN ou package dans static/)
- Bundles JS/CSS inutilises dans `static/`
- `tailwind.css` si non utilise par les consumers MCP

## Contraintes
- Ne jamais casser les routes `/api/mcp-gateway/*`
- Maintenir `scripts/start-mcp-servers.sh` fonctionnel
- Conserver la configuration TOML
- Respecter strictement `codingstandards.md` (async/await, typing, HTTPX, tiktoken, factory DI, francais UI pour endpoints restants)
- Ne supprimer aucune table SQLite MCP
- Architecture 5 couches intacte
