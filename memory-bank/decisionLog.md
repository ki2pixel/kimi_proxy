> 📦 **Archives (pré-2026-04-04)** : [decisionLog_archive.md](file:///home/kidpixel/kimi-proxy/memory-bank/archives/decisionLog_archive.md)

## Décisions Techniques Récentes

### [2026-05-28 12:10:00] - Workflow Docs-Updater et Architecture Pure Middleware
**Problème** : Les métriques de la documentation étaient obsolètes (12049 LOC vs 22532 LOC réels) et l'architecture "Pure Middleware" impliquait de clarifier le statut des docs frontend.
**Décision** : Mettre à jour les compteurs de ligne/fichiers dans les READMEs, et maintenir le statut "ARCHIVE" des anciennes documentations frontend (ex: `docs/features/ui.md`) sans les supprimer.
**Alternatives considérées** :
- Supprimer complètement l'ancienne documentation du frontend (rejeté : perte d'historique sur les patterns).
**Résultat** : La documentation reflète précisément la taille réelle du projet (150 fichiers) tout en conservant la trace de l'ancien dashboard.

### [2026-05-12 02:00:00] - Pivot MCP-first : dépréciation du frontend Dashboard et recentrage sur les features MCP
**Contexte** : L'utilisateur a migré son usage quotidien vers Cline, qui gère automatiquement la fenêtre de contexte avec ses modèles. Le frontend Dashboard (UI vanilla JS, Chart.js, WebSocket visuel, sessions visuelles) est devenu obsolète pour son flux de travail. Son usage passe exclusivement par `scripts/start-mcp-servers.sh` pour orchestrer les serveurs MCP (Shrimp Task Manager, Sequential Thinking, Fast Filesystem, JSON Query, Redis, Postgres, Pruner, etc.).
**Décision** : Recentrer le cœur de Kimi Proxy sur ses features MCP en dépréciant/allégeant le frontend, tout en conservant l'intégrité de l'architecture 5 couches.
**Alternatives considérées** :
- Conserver le frontend tel quel (rejeté : maintenance inutile, ~356KB d'assets statiques non utilisés)
- Extraire le frontend dans un projet séparé (rejeté : sur-ingenierie, pas de valeur ajoutée)
- **Choix** : Déprécier progressivement le frontend (routes UI retirées de main.py, assets statiques supprimés, documentation mise à jour)
**Implémentation** :
- `src/kimi_proxy/main.py` : route `/` remplacée par JSONResponse MCP (status opérationnel, version 2.0.0-mcp). Mount `/static` et `/favicon.ico` retirés. Endpoint `/ws` conservé (broadcast générique backend + clients MCP).
- `static/` : suppression de ~356KB de fichiers frontend pur (index.html, ui.js, modals.js, charts.js, similarity-chart.js, sessions.js, cline.js, auto-session.js, compaction.js, accessibility/, css/). Assets MCP génériques conservés (api.js, mcp.js, memory-service.js, utils.js, websocket.js, favicon.ico).
- Architecture 5 couches intacte : API <- Services <- Features <- Proxy <- Core.
- WebSocket manager conservé car utilisé par 12+ modules backend pour broadcast d'événements.
**Résultat** : Kimi Proxy est désormais orienté MCP-first. Le point d'entrée principal reste `scripts/start-mcp-servers.sh`. L'API FastAPI continue de servir les routes `/api/*` et `/api/mcp-gateway/*`.
**Leçons apprises** : Quand un composant (frontend) devient obsolète pour l'usage réel, il faut le marquer comme déprécié rapidement pour réduire la dette technique. Le websocket manager est un service générique indépendant du frontend — sa conservation était critique.

