> 📦 **Archives (pré-2026-04-04)** : [decisionLog_archive.md](file:///home/kidpixel/kimi-proxy/memory-bank/archives/decisionLog_archive.md)

## Décisions Techniques Récentes

### [2026-11-16 22:05:00] - Optimisation des Règles Antigravity et Indexation Projet (.antigravityignore)
**Problème** : L'IDE Antigravity applique un seuil strict d'alerte (~1 000 tokens / 700-750 mots / ~5,5 Ko) par fichier de règle. Trois règles (`codingstandards.md`, `v5.md`, `prompt-injection-guard.md`) dépassaient massivement ce seuil (9,6 à 11,6 Ko, > 1 300 à 1 500 mots), déclenchant l'alerte « You have exceeded the maximum token limit for this file ». De plus, l'absence de `.antigravityignore` forçait l'indexation de plus de 700 Mo de caches et dépôts locaux (`.mypy_cache`, `venv`, `mcp`, `research`).
**Décision** :
- Création de `.antigravityignore` à la racine pour exclure les caches (`.git/`, `venv/`, `mcp/`, `research/`, `shrimp_data/`, `debug/`, `*.db`, caches Python/pytest/mypy/ruff).
- Densification normative intégrale des règles sans aucune perte d'exigence (5 couches, async/await, tiktoken, SonarCloud <= 15, SSE streaming, logs français, mémoire MCP, protocole prompt injection).
- Réduction de 100 % des fichiers `.agents/rules/*.md` sous le seuil strict de 3,5 Ko (< 450 mots).
- Migration du frontmatter de `commit-message-format.md` vers `trigger: model_decision`.
- Correction des références résiduelles `.windsurf` dans `.agents/skills/`.
**Résultat** :
- Empreinte globale des règles inlinées (`always_on`) divisée par 3,2 (-69,2 %, 11,6 Ko vs 37,9 Ko), libérant ~4 800 tokens de contexte par tour.
- Disparition complète de l'alerte de dépassement de limite de tokens dans Antigravity.
- 198/198 tests unitaires et d'intégration validés sans régression.

### [2026-11-15 12:00:00] - fast-filesystem : architecture H+S et politique de chemins A+
**Problème** : le daemon `fast-filesystem` partagé résolvait les chemins relatifs contre son `cwd` (`/home/kidpixel/kimi-proxy`) et acceptait `MCP_ALLOWED_ROOT=/`. Un agent dans un autre projet lisait silencieusement le mauvais dépôt ; `/etc` était accessible.
**Décision** :
- Garder un daemon HTTP unique (features gateway : cache, pruning, circuit breaker) et utiliser `scripts/mcp_bridge.py` comme transport workspace-aware.
- `MCP_ALLOWED_ROOT=/home/kidpixel` ; toute autre racine explicite est configurable, `/` est refusé au démarrage.
- Clients HTTP directs : chemins absolus uniquement (`-32602 RELATIVE_PATH_UNSUPPORTED`).
- OpenCode : `fast-filesystem` en local stdio via le bridge, qui injecte `params._meta["ai.kimi-proxy/workspaceRoot"]`.
- Politique A+ : un relatif doit rester dans le workspace ; un absolu explicite reste autorisé sous `/home/kidpixel`.
**Alternatives considérées** :
- Vrai serveur stdio par workspace (rejeté : duplication du serveur, perte du cache/pruning gateway).
- Isolation stricte B (rejeté pour l'instant : casse les lectures inter-projets explicites ; à reconsidérer si des agents non fiables sont dans le modèle de menace).
- Paramètre d'outil `workspace_root` (rejeté : schéma pollué, contrôlé par le modèle, redondant avec l'absolu).
**Implémentation** : `scripts/mcp_servers/fast_filesystem_server.py`, `scripts/mcp_servers/path_policy.py`, `scripts/mcp_bridge.py`, `scripts/start-mcp-servers.sh`, `.env` (local), `~/.config/opencode/opencode.json`, skills/règles/docs.
**Résultat** : **198 tests passés** ; validation live OK (relatif correct, évasion refusée, absolu inter-projet OK, `/etc` refusé, loopback, CORS retiré).
**Leçons apprises** : un serveur MCP partagé ne doit jamais utiliser son `cwd` comme base de résolution ; les descriptions d'outils et les skills doivent refléter le schéma réel et imposer l'absolu. Le fail-closed est préférable à un succès silencieux sur le mauvais workspace.

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

