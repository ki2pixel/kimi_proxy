## Tâche en cours
Aucune

### [2026-02-27 15:58:00] - Phase DeepInfra Pruner (Tasks 1→6) : implémentation + tests + documentation - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Finaliser la chaîne DeepInfra pour MCP Pruner de bout en bout, en conservant la compatibilité proxy et un mode fail-open robuste (env > TOML, fallback heuristique), puis clôturer avec tests et documentation FR.

**Livrables** :
- Task 1: client DeepInfra async `src/kimi_proxy/features/mcp_pruner/deepinfra_client.py` (HTTPX, parsing best-effort, exceptions typées).
- Task 2: moteur pruning DeepInfra `src/kimi_proxy/features/mcp_pruner/deepinfra_engine.py` (top-K lignes, markers/annotations canoniques).
- Task 3: intégration serveur `src/kimi_proxy/features/mcp_pruner/server.py` (sélection backend `KIMI_PRUNING_BACKEND`, priorité `env > toml`, cache TTL in-memory, métriques coût/tokens, fail-open).
- Task 4: fallback TOML + loader backend pruner (`config.toml` + loader config), avec priorité finale `env > toml`.
- Task 5: tests DeepInfra/fallback/compat proxy:
  - `tests/unit/features/test_mcp_pruner_deepinfra.py`
  - `tests/integration/test_proxy_context_pruning_c2.py`
- Task 6: documentation FR enrichie `docs/features/mcp-pruner.md` (DeepInfra opt-in, env vars, troubleshooting 401/429/timeout/parse, rollback).

**Validation** :
- Shrimp: **6/6 tâches complétées** (Tasks 1→6 marquées completed).
- Tests Task 5: `./bin/kimi-proxy test tests/unit/features/test_mcp_pruner_deepinfra.py tests/integration/test_proxy_context_pruning_c2.py -q` ✅.
- Vérification doc Task 6: sections DeepInfra + troubleshooting présentes, alignées runtime (`env > config.toml`, stats/warnings, fail-open).

**Notes** :
- Correctif test critique: conservation d’un `REAL_HTTPX_ASYNC_CLIENT` pour éviter l’effet de bord du monkeypatch de `pruner_server.httpx.AsyncClient` sur le client ASGI du test runner.
- Le backend cloud reste strictement **opt-in**; l’heuristique locale demeure la voie par défaut.

### [2026-02-27 00:58:00] - Incident démarrage MCP Pruner (port 8006) + validation globale MCP - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Diagnostiquer et corriger l’échec de démarrage du serveur MCP Pruner pendant `./start.sh`, puis valider le redémarrage complet MCP sans régression.

**Livrables** :
- Correctif robustesse readiness pruner: `scripts/start-mcp-servers.sh`
  - remplacement `sleep 2` par boucle d’attente bornée (12s),
  - vérification process vivant via `kill -0`,
  - diagnostic actionnable (`tail -n 80 /tmp/mcp_pruner.log`) en échec.
- Correctif wrapper global: `start.sh` pointe vers `bin/kimi-proxy`.
- Documentation troubleshooting: `docs/features/mcp-pruner.md` (RCA + commandes de vérification + log vide non bloquant).

**Validation** :
- Restart MCP OK + status OK.
- Ports en écoute: 8001/8003/8004/8005/8006 (et 8000 dashboard) confirmés.
- Probes pruner: `GET /health` OK, JSON-RPC `initialize` OK.
- Non-régression: `./bin/kimi-proxy test` → **134 passed**.

**Notes** :
- Un process orphelin sur `:8000` peut fausser la validation globale; nettoyage requis avant certains runs.
- `/tmp/mcp_pruner.log` peut rester vide en démarrage nominal (`uvicorn` warning + access_log off).

## Tâches Complétées

### [2026-02-26 20:41:00] - MCP ripgrep-agent : timeouts `-32001` (bridge stdio) + configs + docs + vérification - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Éliminer les timeouts / erreurs `-32001` observés avec `ripgrep-agent` via le bridge stdio (RCA: limite ~64KiB de `StreamReader.readline()` sur stdout quand une réponse JSON-RPC 1-ligne est trop volumineuse).

**Livrables** :
- Bridge: `scripts/mcp_bridge.py`
  - `MCP_BRIDGE_STDIO_STREAM_LIMIT` configurable (défaut 8MiB, clamp 64KiB–64MiB) appliqué à stdin bridge + pipes subprocess.
  - Suivi best-effort des IDs JSON-RPC inflight + émission immédiate d’erreurs JSON-RPC `-32001` en cas d’overrun stdout (pas de hang IDE).
- Tests unitaires: `tests/unit/test_mcp_bridge.py` mis à jour (validation -32001 sur dépassement limite).
- Configs (repo): `config.yaml`, `cline_mcp_settings.json`, `mcp_config.json`
  - `MCP_BRIDGE_MONITORING_LOG_PATH` distinct par serveur (filesystem/ripgrep/shrimp).
  - `MCP_BRIDGE_STDIO_STREAM_LIMIT=8388608` (8MiB) explicite pour `ripgrep-agent`.
- Docs troubleshooting:
  - `docs/troubleshooting/MCP_Bridge_Stdio_Servers.md` (RCA + runbook + env `MCP_BRIDGE_STDIO_STREAM_LIMIT`).
  - `docs/troubleshooting/MCP_IDE_Interop.md` (diagnostic `-32001`: `unknown_server` vs stdout limit + runbook).
- Harness offline déterministe (sans dépendre de `npx`/réseau):
  - `tests/fixtures/fake_mcp_server_stdio.py`
  - `tests/mcp/harness_bridge_stdio_limits.py`

**Validation** :
- Suite: `./bin/kimi-proxy test` → **134 passed**.
- Harness: `python3 tests/mcp/harness_bridge_stdio_limits.py` → **OK**.

**Notes** :
- Les tests/harness évitent les blocages possibles liés au démarrage `npx` (download/cache).
- Si l’IDE utilise un fichier de config hors repo (ex: VS Code/Cline), vérifier le chemin réellement chargé.

### [2026-02-26 16:50:00] - Docs Updater: parité runtime API + clarification MCP/Gateway + pruner A2 - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Synchroniser la documentation avec l’état runtime réel après audit structurel et vérification code-first.

**Livrables** :
- `docs/api/README.md` réécrit avec inventaire runtime monté (58 routes effectives, 56 méthode+chemin uniques), corrections de chemins compaction et suppression bulk sessions.
- `docs/features/mcp.md` clarifié pour distinguer UI Phase 3/4, source backend de statuts (2 serveurs spécialisés) et capacité gateway (5 serveurs routables).
- `docs/features/mcp-pruner.md` enrichi d’une section d’alignement implémentation A2 (handshake, alias `recover_range`, fail-open, TTL, variables d’environnement).

**Validation** :
- Comptage décorateurs routes: `60`.
- Comptage runtime FastAPI monté: `58` routes HTTP effectives, `56` couples méthode+chemin uniques.
- Vérification mapping gateway: `context-compression`, `sequential-thinking`, `fast-filesystem`, `json-query`, `pruner`.

**Notes** :
- Aucun changement de code applicatif; documentation et traçabilité uniquement.
- Le décalage décorateurs/runtime est explicitement documenté pour éviter les futures dérives.

### [2026-02-26 16:12:00] - MCP Pruner : C1 spec transparence/recovery + C2 intégration /chat/completions - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** :
- C1: clarifier et harmoniser le contrat de transparence + recovery (annotations/markers/ranges, erreurs, fail-open).
- C2: intégrer un appel au serveur MCP Pruner local dans `/chat/completions` avant token counting et avant envoi provider, sous feature flag et avec fallback no-op.

**Livrables** :
- Spec mise à jour: `docs/features/mcp-pruner.md` (markers canonique, règle d’identité marker↔annotation, recovery ranges, erreurs -32004/-32005, fail-open, exemples `curl`).
- Config: `config.toml` + loader `ContextPruningConfig` dans `src/kimi_proxy/config/loader.py`.
- Proxy pruning (I/O HTTP local): `src/kimi_proxy/proxy/context_pruning.py`.
- Intégration pipeline: `src/kimi_proxy/api/routes/proxy.py`.
- Tests intégration: `tests/integration/test_proxy_context_pruning_c2.py`.

**Validation** :
- `python3 -m compileall -q src/kimi_proxy/config/loader.py src/kimi_proxy/proxy/context_pruning.py src/kimi_proxy/api/routes/proxy.py`.
- `pytest -q tests/integration/test_proxy_context_pruning_c2.py tests/integration/test_proxy_observation_masking_schema1.py`.

**Notes** :
- Le pruning est volontairement conservateur: il ne modifie que les messages `role="tool"` (préservation stricte des invariants tool-calling).
- Logs uniquement metadata-only (pas de contenu pruné).

### [2026-02-26 13:03:30] - Observation Masking Schéma 1 : benchmark offline + documentation - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Documenter et valider opérationnellement le masking conversationnel Schéma 1 (masquage des anciens `role="tool"` via fenêtre en *tours tool*), et fournir un benchmark offline pour mesurer l’impact tokens/chars.

**Livrables** :
- Fixture tool-heavy : `tests/fixtures/schema1_tool_heavy.json`
- Benchmark offline : `scripts/bench_observation_masking_schema1.py` (zéro réseau, sortie stable `--json`, exécutable via `python3` sans installer le package)
- Documentation : `docs/WIP/schema1_observation_masking.md`
- README : ajout d’une section “Schéma 1 : Observation Masking” (lien doc + activation config + commande benchmark)

**Validation** :
- Benchmark : `python3 scripts/bench_observation_masking_schema1.py --json --window-turns 1`
- Suite de tests : `./bin/kimi-proxy test` → **120 passed**

**Notes** :
- La doc clarifie la différence entre Schéma 1 (messages envoyés au provider) et le masking JSON-RPC du MCP Gateway (anti log-bomb).

### [2026-02-25 21:08:30] - Monitoring MCP Bridge stdio : compteurs + JSONL opt-in - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Ajouter un monitoring simple pour les serveurs MCP relayés en stdio via `scripts/mcp_bridge.py` (filesystem-agent, ripgrep-agent, shrimp-task-manager), sans jamais corrompre le flux JSON-RPC sur stdout.

**Solution** :
- Ajout d’un `BridgeMonitor` opt-in activé via env vars (`MCP_BRIDGE_MONITORING_*`).
- Compteurs en mémoire (requêtes par `method`, réponses totales et erreurs).
- Logging JSONL optionnel (metadata-only; jamais `params`, `result`, `error`).
- Écritures non-bloquantes (queue asyncio + `asyncio.to_thread`) et gestion backpressure (drops).
- Instrumentation sur stdin→child.stdin, stdout child filtré→stdout, et shim Shrimp `roots/list`.

**Tests** :
- `tests/unit/test_mcp_bridge.py` étendu (BridgeMonitor + overflow queue).
- Suite complète: `./bin/kimi-proxy test` → **109 passed**.

**Docs** :
- `docs/troubleshooting/MCP_Bridge_Stdio_Servers.md` : ajout section Monitoring (activation, format JSONL, sécurité, trade-offs).

**Variables d’environnement (nouveau)** :
- `MCP_BRIDGE_MONITORING_ENABLED`
- `MCP_BRIDGE_MONITORING_LOG_PATH`
- `MCP_BRIDGE_MONITORING_QUEUE_MAX`
- `MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT`

### [2026-02-25 18:40:00] - Interop MCP IDE (Windsurf/Cline/Continue) : stdio bridge + shim roots/list + configs repo - TERMINÉ
**Statut** : ✅ COMPLETÉ

**Objectif** : Corriger les échecs de connexion MCP dans **Windsurf** et **Cline** pour :
- `filesystem-agent`
- `ripgrep-agent`
- `shrimp-task-manager`

**Cause racine** : Le **MCP Gateway HTTP** de Kimi Proxy ne mappe pas ces serveurs stdio. `get_mcp_server_base_url()` ne connaît que : `context-compression`, `sequential-thinking`, `fast-filesystem`, `json-query` → les autres retournent `unknown_server` (JSON-RPC `-32001`, HTTP 404).

**Correctif appliqué** :
- Alignement Windsurf/Cline sur Continue.dev : lancement des 3 serveurs en **stdio** via `python3 scripts/mcp_bridge.py <server>`.
- Stabilisation Shrimp Task Manager : ajout dans `scripts/mcp_bridge.py` d’un **shim** qui intercepte la requête server→client `roots/list` et répond automatiquement avec une racine workspace (`file://...`).

**Configs modifiées (repo)** :
- `mcp_config.json` (Windsurf) : `filesystem-agent`, `ripgrep-agent`, `shrimp-task-manager` → stdio bridge + env (`MCP_FILESYSTEM_ALLOWED_ROOT`, `MCP_SHRIMP_TASK_MANAGER_COMMAND`, `DATA_DIR=/home/kidpixel/kimi-proxy/shrimp_data`).
- `cline_mcp_settings.json` (Cline) : bascule `type: "stdio"` pour ces 3 serveurs + conservation du reste en gateway HTTP.
- `config.yaml` (Continue.dev) : lu uniquement (pas modifié durant cette session).

**Validation** :
- Curl OK via gateway pour les serveurs HTTP (ex: `sequential-thinking`).
- Harness Python OK pour `shrimp-task-manager` : `initialize` → `tools/list` → `tools/call` (dont `split_tasks`).

**Points à faire (suite)** :
- Vérifier/aligner les **configs réellement utilisées** par les IDE (hors repo) : `../.cline/data/settings/cline_mcp_settings.json` et `../.codeium/mcp_config.json`.
- Exécuter le workflow Shrimp *via l’outil MCP* : `plan_task` → `analyze_task` → `split_tasks`, puis `execute_task` + `verify_task`.
- Phase 5 : validation structure JSON/YAML + tests manuels dans Windsurf/Cline/Continue.dev + mise à jour documentation (interop + roots/list shim).

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