## Tâche en cours
Aucune

## Tâches Complétées

### [2026-02-25 14:25:00] - MCP Bridge stdio (filesystem-agent, ripgrep-agent, shrimp-task-manager) + configs + tests + doc - TERMINÉ
**Statut** : ✅ COMPLETÉ
**Description** : Ajout d’un bridge `scripts/mcp_bridge.py` supportant (1) forward HTTP vers le MCP Gateway pour les serveurs MCP HTTP existants et (2) relay stdio pour lancer des serveurs MCP locaux (filesystem-agent, ripgrep-agent, shrimp-task-manager). Filtrage stdout: seul le JSON-RPC (`{\"jsonrpc\":\"2.0\"}`) est forwardé vers stdout; les bannières/logs sont redirigés vers stderr.

**Config IDE** : `config.yaml` mis à jour pour lancer ces serveurs via `python3 scripts/mcp_bridge.py <server>`; suppression du doublon `switchbot-postgres`.

**Tests** : ajout `tests/unit/test_mcp_bridge.py` + exécution suite complète OK (`./bin/kimi-proxy test` → 103 passed).

**Docs** : ajout `docs/troubleshooting/MCP_Bridge_Stdio_Servers.md` + liens depuis `docs/troubleshooting/Continue.dev-MCP-Local-Server-Configuration.md` et `docs/features/mcp.md`.

### [2026-02-25 10:58:40] - MCP — Accès fichiers étendu à `/home/kidpixel/*` + stabilisation gateway - TERMINÉ
**Statut** : ✅ COMPLETÉ
**Description** : Les serveurs MCP locaux (Phase 4) n’autorisaient que le workspace `/home/kidpixel/kimi-proxy` (403 hors workspace). L’accès a été étendu à **tous les workspaces sous `/home/kidpixel/`** via une racine unique `MCP_ALLOWED_ROOT` (fallback compat `WORKSPACE_PATH`). La validation de chemins a été durcie contre : path traversal (`..`) et symlink escape (résolution + `relative_to`).

**Gateway** : Correction côté proxy pour éviter de transformer un refus d’accès 403 upstream en 502; le gateway forwarde désormais la réponse JSON-RPC d’erreur telle quelle.

**Fichiers modifiés / ajoutés** :
- `scripts/start-mcp-servers.sh`
- `src/kimi_proxy/proxy/mcp_gateway_rpc.py`
- `tests/mcp/test_mcp_allowed_root_e2e.py`
- `README.md`
- `docs/features/mcp.md`
... [KIMI_PROXY_OBSERVATION_MASKED original_chars=28078 head=2000 tail=2000] ...
ut** : 1000+ msg/sec
- **MCP response time** : < 30s (Task Master), < 10s (Filesystem)

### Qualité
- **Coverage tests** : 85%+ (core), 70%+ (features)
- **Code quality** : SonarQube A-grade
- **Documentation** : 100% modules documentés
- **Type coverage** : 95%+ annotations

### Utilisation
- **Tokens économisés** : 20-40% via sanitizer/compression
- **Sessions actives** : 3-5 simultanées
- **Providers utilisés** : 5/8 régulièrement
- **MCP tools usage** : 200+ appels/jour

### [2026-02-24 15:27:00] - **Workflow Docs-Updater Exécuté TERMINÉ**
**Statut** : ✅ COMPLETÉ
**Description** : Audit structurel complet (7387 LOC Python, 60 routes API, 703 fonctions JS). Mise à jour documentation API (ajout section Cline, correction métriques), création documentation Cline (features/cline.md), mise à jour README avec métriques projet. Conforme documentation/SKILL.md appliqué.

**Audit structurel** :
- Architecture 5 couches confirmée (46 répertoires, 122 fichiers)
- 7387 LOC Python (61 fichiers) vs 8392 précédemment
- 60 routes API détectées vs 53 documentées
- 703 fonctions/classes JavaScript dans 17 modules ES6
- 685 éléments HTML avec IDs/classes structurés
- 58 opérations SQL dans base de données

**Mises à jour appliquées** :
- docs/api/README.md : Ajout section Cline, correction métriques (60 routes, 7387 LOC, 61 fichiers)
- docs/features/cline.md : Création documentation complète intégration Cline (bridge API, sécurité DOM, patterns système)
- docs/README.md : Ajout section métriques projet avec détail par couche

**Skill documentation/SKILL.md appliqué** :
- TL;DR ✔ : Résumés concis en début de chaque fichier
- Problem-First ✔ : Problèmes avant solutions
- Comparaison ❌/✅ ✔ : Exemples pratiques
- Trade-offs ✔ : Tableaux avantages/inconvénients
- Golden Rule ✔ : Règles impératives

**Impact** : Documentation synchronisée avec état actuel du code, nouvelles fonctionnalités Cline documentées, métriques projet à jour.