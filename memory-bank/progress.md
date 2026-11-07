> 📦 **Archives (pré-2026-04-04)** : [progress_archive.md](file:///home/kidpixel/kimi-proxy/memory-bank/archives/progress_archive.md)

## Tâche en cours
Aucune tâche active.

## Dernière session terminée
### [2026-11-07 11:05:00] **Rétablissement du démarrage automatique systemd — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Garantir le démarrage automatique du proxy et des serveurs MCP HTTP après un redémarrage système.

**Cause racine** :
- `kimi-proxy.service` était `enabled` et `Linger=yes`, mais son `ExecStart` appelait `scripts/start-systemd.sh`, absent du dépôt. Le service redémarrait en boucle avec `status=127`.
- `~/.local/bin/kimi-proxy` était un ancien entry point du paquet `kimi-proxy-dashboard`, sans lien avec le CLI du dépôt.
- Les lanceurs desktop pointaient vers `scripts/start.sh`, également absent.

**Actions réalisées** :
- Recréation de `scripts/start-systemd.sh` : chargement robuste de `.env`, activation du venv, démarrage idempotent des serveurs MCP, puis `exec python -m kimi_proxy --host 127.0.0.1 --port 8000` au premier plan.
- `~/.local/bin/kimi-proxy` remplacé par un symlink vers `/home/kidpixel/kimi-proxy/bin/kimi-proxy`.
- `~/.local/share/applications/kimi-proxy.desktop` et `~/.config/autostart/start.sh.desktop` corrigés pour appeler `/usr/bin/systemctl --user start kimi-proxy`.
- `bin/kimi-proxy` rendu systemd-aware : `status`, `stop`, `restart` et `start` détectent le service actif au lieu de dépendre uniquement de `.server.pid`.

**Validation** :
- `systemctl --user is-enabled kimi-proxy` → `enabled` ; `is-active` → `active` ; `Linger=yes`.
- `systemctl --user restart kimi-proxy` et `kimi-proxy restart` : proxy prêt en 12 s, ports 8000 à 8006 en écoute.
- `kimi-proxy status` affiche le service systemd actif ; `kimi-proxy start` refuse un doublon.
- `tools/list` OK via la gateway (`fast-filesystem`, `json-query`, `sequential-thinking`) et en direct sur `mcp-pruner`.
- `bash -n bin/kimi-proxy scripts/start-systemd.sh` : OK.
- `./bin/kimi-proxy test -q` : **172 passed**.

### [2026-11-07 03:00:00] **Correctif reloader et rétablissement des MCP HTTP — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Rétablir les serveurs MCP HTTP (gateway et pruner) après les erreurs « fetch failed » constatées dans Command Code, OpenCode et Antigravity.

**Cause racine** :
- Le reloader `watchfiles` d'uvicorn surveillait tout le dépôt et traversait `workspace/mcp_allowed_root_test/etc_link -> /etc`. Le répertoire `/etc/redis` est inaccessible à l'utilisateur, ce qui provoquait une `PermissionError` et faisait tomber le reloader. Les ports 8000 à 8006 n'étaient plus en écoute.

**Actions réalisées** :
- `bin/kimi-proxy` utilise désormais `--reload-dir "$PROJECT_DIR/src"` : le reload ne surveille plus `workspace/`, `tests/` ni les liens symboliques hors `src/`.
- Suppression du lien de test obsolète `workspace/mcp_allowed_root_test/etc_link`.
- Redémarrage complet via `./bin/kimi-proxy start --reload`.

**Validation** :
- Ports 8000, 8001, 8003, 8004, 8005 et 8006 en écoute.
- `/health` répond `200` sur les six ports.
- `tools/list` OK via la gateway pour `fast-filesystem`, `json-query`, `sequential-thinking`, et en direct pour `mcp-pruner`.
- `./bin/kimi-proxy test -q` : **172 passed**.
- `bash -n bin/kimi-proxy` : OK.

### [2026-11-06 23:55:00] **Durcissement des configs MCP IDE — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Aligner les configurations MCP externes (Command Code, Antigravity, OpenCode) sur la politique de sécurité et de cohérence du dépôt.

**Actions réalisées** :
- `MCP_FILESYSTEM_ALLOWED_ROOT` corrigé de `/` vers `/home/kidpixel` dans `~/.commandcode/mcp.json` et `~/.config/opencode/opencode.json`.
- Logs de monitoring corrigés dans Antigravity et OpenCode : `mcp-bridge-ripgrep.jsonl` et `mcp-bridge-shrimp.jsonl` au lieu du fichier filesystem partagé.
- Secrets Antigravity (Redis, Neon, Supabase) déplacés vers `~/.config/kimi-proxy/mcp-secrets/` avec répertoire `700` et fichiers `600`.
- Ajout du wrapper `scripts/mcp_secret_exec.py` et du test `tests/unit/test_mcp_secret_exec.py`. Le wrapper charge un `.env`, étend les variables `${VAR}` dans les arguments puis exécute la commande MCP via `execvpe`.
- Aucun secret ne subsiste dans `~/.gemini/antigravity-ide/mcp_config.json`.

**Validation** :
- Les trois fichiers de configuration restent des JSON valides.
- Chargement des trois fichiers de secrets vérifié sans afficher les valeurs.
- `./bin/kimi-proxy test -q` : **172 passed**.
- `venv/bin/python -m ruff check scripts/mcp_secret_exec.py tests/unit/test_mcp_secret_exec.py` : **All checks passed**.

### [2026-11-06 23:30:00] **Remédiation Audit Backend MCP (ANOM-01 à ANOM-08) — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Appliquer les 8 anomalies de l'audit `docs/audit/Audit-Backend-et-Plan-de-Remediation-MCP.md` sans casser l'architecture middleware session-less.

**Actions réalisées** :
- **ANOM-01 (sockets/SSRF)** : fermeture déterministe de `response` et `_client_ref` sur erreur streaming `>= 400` via `close_stream_resources()` ; blocage systématique des IP privées, réservées, link-local, multicast et non spécifiées, avec loopback autorisé uniquement en développement.
- **ANOM-02 (JSON-RPC)** : interception de `JSONDecodeError`/`UnicodeDecodeError` dans `api_mcp_gateway_rpc` et retour `-32700` HTTP 400 en français.
- **ANOM-03 (5 couches)** : extraction de `forward_jsonrpc` et `MCPGatewayUpstreamError` dans `features/mcp/rpc_transport.py` ; suppression de l'import `config.loader` dans `core/database.py` via `configure_database()` injecté par `main.py`.
- **ANOM-04 (async I/O)** : ajout de `run_db_in_thread()` ; déport SQLite de `MemoryManager` et `sanitizer/storage.py` ; déport de l'encodage `SentenceTransformer` via `asyncio.to_thread` avec verrou de chargement.
- **ANOM-05 (fuites mémoire)** : suppression de `_local_cache` et `_tool_cache` ; `PruneStore` borné à 512 entrées ; purge et plafond de `KimiSessionSource._sessions` ; `failure_reasons` en `deque(maxlen=100)`.
- **ANOM-06 (auth)** : `secrets.compare_digest` et relecture dynamique de `KIMI_ENV`/`KIMI_ADMIN_KEY` via `_get_admin_key()` ; messages 401 et `ConfigurationError` francisés.
- **ANOM-07 (complexité/code mort)** : découpage de `_tool_prune_text` et `maybe_prune_jsonrpc_response` en sous-fonctions ; pipeline pur `run_repair_pipeline` sans `ast.literal_eval` ; suppression de `features/mcp/client.py.backup` ; migration du pruner vers `lifespan`.
- **ANOM-08 (CLI/tests/docs)** : parsing `.env` en Bash pur sans `xargs` ; aide `--host 127.0.0.1` ; import de test corrigé ; test `eval` factice remplacé ; nouveaux tests streaming, `-32700`, `PruneStore`, sessions, auth et CLI ; docs `mcp.md`, `passthrough.md` et `tool-validation.md` synchronisées.

**Fichiers modifiés** : `bin/kimi-proxy`, `src/kimi_proxy/{main.py,api/dependencies.py,api/routes/mcp_gateway.py,api/routes/sanitizer.py,core/database.py,proxy/{passthrough.py,stream.py,context_pruning.py,tool_utils.py},features/mcp/{client.py,memory.py,__init__.py},features/mcp_pruner/{server.py,local_rag.py},features/mcp_tool_pruning/engine.py,features/log_watcher/watcher.py,features/sanitizer/storage.py}`, `docs/features/mcp.md`, `docs/proxy/{passthrough.md,tool-validation.md}`, tests unitaires/e2e associés.

**Validation** :
- `./bin/kimi-proxy test -q` : **170 passed**, 0 échec.
- `venv/bin/python -m ruff check src ...` : **All checks passed**.
- `bash -n bin/kimi-proxy` : OK.
- Contrôle AST : aucune utilisation de `get_db()` dans une fonction `async def` de `memory.py` ou `storage.py`.
- `grep` : aucune dépendance `Proxy -> API`, `Core -> Config`, ni résidu `_local_cache`/`_tool_cache`/`literal_eval`.

### [2026-11-06 22:45:00] **Commit & Push vers origin/main — TERMINÉ**
**Statut** : ✅ COMPLETÉ
**Objectif** : Validation des tests, commit des modifications de documentation/configuration et push vers `origin/main`.
**Actions réalisées** :
- Exécution de la suite de tests (`./bin/kimi-proxy test -q`) : 155 passants, 0 régression.
- Création du commit `a2066a6` (`docs: update agent configuration and system rules`).
- Push de la branche `main` vers `origin/main` (4 commits synchronisés : `8568596`, `de68ade`, `5f65382`, `a2066a6`).

### [2026-07-15 14:20:00] **Configuration Zencoder MCP Gateway (Option A) — TERMINÉ**
**Statut** : ✅ COMPLETÉ
**Objectif** : Configurer l'intégration de Zencoder avec le Gateway HTTP de `kimi-proxy`.
**Actions réalisées** :
- Création du fichier `.zencoder/settings.json` local au projet.
- Configuration des serveurs compatibles Gateway (`fast-filesystem`, `json-query`, `sequential-thinking`, `mcp-pruner` via `pruner/rpc`) pour attaquer l'adresse HTTP `http://localhost:8000/api/mcp-gateway/.../rpc`.
- Préservation des serveurs d'arrière-plan/spécifiques (`filesystem-agent`, `ripgrep-agent`, `shrimp-task-manager`) en mode Direct Stdio via le script `scripts/mcp_bridge.py`.

### [2026-07-15 01:20:00] **Remédiations Sécurité et Stabilité Backend (Audit 2026-07-15) — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Résoudre l'ensemble des vulnérabilités critiques (P0), dysfonctionnements majeurs (P1) et dettes techniques (P2) identifiés dans le rapport d'audit du 15 juillet 2026.

**Actions réalisées** :
- **Sécurité Critique (P0)** : Remplacement de `eval` par `ast.literal_eval` dans `tool_utils.py` ; restriction des interfaces d'écoute à `127.0.0.1` par défaut ; implémentation de l'authentification obligatoire `verify_admin_key` sur les routes sensibles d'administration ; durcissement CORS avec expressions régulières en mode développement ; limitation de taille de payload à 10 Mo ; validation SSRF stricte avec résolution DNS sur `X-Target-Base-URL`.
- **Stabilisation Fonctionnelle (P1)** : Correction de la réponse réussie non-streaming retournée en erreur dans `proxy.py` ; résolution de toutes les NameErrors Ruff `F821` (dont compaction et imports manquants) ; masquage complet des clés API dans les logs ; migration de l'authentification Gemini vers l'entête HTTP `x-goog-api-key` ; limitation du buffer SSE à 256 Ko dans `stream.py` ; corrections de la compaction dans `compaction.py` (évitement double persistance, correctif `totals`, arrêt messages fictifs en production) ; désactivation du stockage par défaut de `original_content` dans le sanitizer et implémentation d'un chiffrement symétrique pure Python en mode CTR (avec PBKDF2) si activé.
- **Durcissement et Maintenabilité (P2)** : Désactivation de `mcp_tool_pruning` et `persist_sessions` par défaut ; limitation de `_GATEWAY_CACHE` à 512 clés (éviction FIFO) et isolation via `copy.deepcopy` ; épuration de `/health` pour retourner uniquement un statut minimal sans fuite de configuration, déplacement des détails de diagnostics détaillés et du statut de rate limit vers le route d'administration protégé `/api/admin/health` ; ajout de `bandit` dans `requirements-dev.txt`.
- **Validation (P3)** : Résolution de ~200 erreurs Ruff, 110+ erreurs MyPy, 7 alertes Bandit Low (via `# nosec`), isolation de l'environnement hôte pour la configuration de pruning MCP (`os.getenv` mocké), et passage des 236 cas de tests unitaires et d'intégration (100% passed).

### [2026-07-12 23:35:00] **Correction routage mcp-pruner dans le pont MCP — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Configurer et router correctement le serveur `mcp-pruner` via `mcp_bridge.py`.

**Actions réalisées** :
- Ajout de `mcp-pruner` dans `GATEWAY_HTTP_SERVERS` dans `scripts/mcp_bridge.py`.
- Routage du nom `mcp-pruner` vers `pruner` dans `_get_gateway_url` pour correspondre à l'API Gateway.
- Validation par exécution de la suite de tests unitaires (197 tests passés).

### [2026-07-04 12:30:00] **Transition Minimaliste Kimi Proxy (Audit Backend) — TERMINÉ**
**Statut** : ✅ COMPLÉTÉ (5/5 tâches)

**Objectif** : Transformer Kimi Proxy en middleware minimal et performant selon les recommandations de `docs/audit/audit_backend_kimi-proxy.md`.

**Actions réalisées** :
- **Task 1 - Log Watcher** : Désactivé par défaut (`LOG_WATCHER_ENABLED=false`), configurable via env/TOML.
- **Task 2 - MCP Pruning** : `[mcp_tool_pruning] enabled = false` explicite dans les configs.
- **Task 3 - Session Persistence** : SQLite optionnel, mode in-memory par défaut (SQLite `:memory:` partagée), cache TTL 2s sur `get_active_session()`, configurable via `KIMI_PERSIST_SESSIONS`.
- **Task 4 - MCP Gateway** : `forward_jsonrpc` + `MCPGatewayUpstreamError` consolidés dans `api/routes/mcp_gateway.py`. Stub rétro-compat dans `proxy/mcp_gateway_rpc.py`.
- **Task 5 - Observation Masking** : `_looks_like_error_tool_content` simplifié (frozenset structurel, faux positifs éliminés). Helper `build_mask_policy_from_config()` centralisé.

**Fichiers modifiés** : `config.toml`, `config.toml.minimal`, `loader.py`, `main.py`, `database.py`, `mcp_gateway.py`, `mcp_gateway_rpc.py`, `context_pruning.py`, `schema1.py`, `__init__.py`, `proxy.py`, `passthrough.py`.
**Fichiers de test ajoutés** : `test_config_log_watcher.py`, `test_database_optional_persistence.py`, `test_observation_masking_consolidated.py`.
**Validation** : 233/233 tests passés.

### [2026-06-19 20:15:00] **Paramétrage et assouplissement du Circuit Breaker MCP — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Configurer dynamiquement le circuit breaker MCP via `config.toml` et assouplir son comportement par défaut (HTTP 429) pour éviter les limitations intempestives sur les outils MCP locaux.

**Actions réalisées** :
- Ajout des constantes par défaut dans `constants.py` (`DEFAULT_MCP_CB_MAX_FAILURES = 5`).
- Surcharge supportée via `config.toml` sous la section `[mcp.gateway]`.
- Implémentation du parsing dans `loader.py` et intégration dynamique à chaque appel tools/call dans `mcp_gateway.py`.
- Ajout de tests unitaires et d'intégration dans `test_mcp_gateway.py`.
- Validation complète via `./bin/kimi-proxy test` (192/192 succès).

### [2026-06-04 13:01:00] **Mise à Jour de la Documentation (docs-updater) — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Auditer, recalculer et harmoniser toutes les métriques de code de production et d'API suite au pivot MCP-first de Kimi Proxy.

**Actions réalisées** :
- Audit des fichiers de production : 87 fichiers Python, 14 177 LOC, complexité Grade A (3.95).
- Audit des routes FastAPI : 44 routes HTTP effectives, 10 fichiers de routes actifs.
- Audit des migrations DB : 14 opérations ALTER TABLE appliquées automatiquement au démarrage.
- Mise à jour de `README.md` (root), `docs/README.md`, `docs/architecture/README.md`, `docs/api/README.md` et `docs/core/README.md`.
- Validation complète via `./bin/kimi-proxy test` (189/189 succès).

### [2026-06-04 12:56:00] **Audit et Mise à Jour des Compétences Kimi Proxy — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Auditer et mettre à jour les compétences dans `.agents/skills/` pour correspondre à la Phase 3.

**Actions réalisées** :
- Mise à jour de `kimi-proxy-mcp-integration` et `kimi-proxy-performance-optimization` (suppression des références "session").
- Ajout de la documentation du contournement de capability "roots" de `filesystem-agent` dans `fast-filesystem-ops`.
- Ajout de validation dynamique des métriques dans `docs-updater`.
- Validation par `./bin/kimi-proxy test` (189/189 succès).

### [2026-06-03 21:19:00] **Refactoring Complexité Cognitive (Phase 1, 2, 3) — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Analyser le rapport SonarCloud et assainir la base de code en résolvant les vulnérabilités de sécurité, les bugs (paramètres redondants) et en diminuant drastiquement la complexité cognitive (S3776) des composants centraux du Proxy.

**Actions réalisées** :
- Phase 1 (Sécurité & Fiabilité) : Fix des répertoires temporaires (S5443), correctifs de typage et standardisation de la capture d'exception.
- Phase 2 (Simplification & Refactoring) : Extraction de logique pour réduire la complexité de la route `/chat/completions` dans `proxy.py`, du générateur dans `stream.py`, du circuit-breaker dans `mcp_gateway.py`, et des mécanismes de relai I/O asynchrones dans `mcp_bridge.py`.
- Phase 3 (Nettoyage & Redondance) : Suppression des paramètres inutilisés (S1172), sécurisation des conditions bash (`[[`) (S7688), et centralisation de constantes globales (S1192).
- Validation rigoureuse via la suite de tests (`./bin/kimi-proxy test`) : 189/189 tests en succès (100%), garantissant l'absence de régression.
- Nettoyage des artefacts de refactoring à la racine du projet.

### [2026-05-28 12:10:00] **Workflow Docs-Updater — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Exécuter le skill docs-updater pour harmoniser la documentation et les métriques (Audit cloc, radon).

**Actions réalisées** :
- Audit structurel : 150 fichiers Python, 22532 LOC (vs 12049 précédemment), 62 routes API, 118 opérations SQL.
- Mise à jour des métriques dans `README.md` et `docs/README.md`.
- Vérification de la documentation : les documents obsolètes comme `docs/features/ui.md` sont déjà correctement flaggés comme archives (Frontend déprécié).

### [2026-05-22 14:50:00] **Bypass Workspace Roots filesystem-agent — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Empêcher le serveur MCP `@modelcontextprotocol/server-filesystem` (lancé sous l'alias `filesystem-agent`) d'écraser la racine autorisée par défaut (`/home/kidpixel`) avec les workspace roots fournies par l'IDE (comme Windsurf ou Antigravity) via le protocole dynamic roots (`roots/list`), ce qui interdisait l'écriture dans des dossiers en dehors du workspace actif (ex: `~/.windsurf/plans/`).

**Actions réalisées** :
- Diagnostic du comportement de `@modelcontextprotocol/server-filesystem` qui requête dynamiquement les roots via dynamic roots capability si déclarée par l'IDE, écrasant ainsi la configuration CLI.
- Modification chirurgicale de `scripts/mcp_bridge.py` au niveau du filtrage `client_to_server` lors du handshake `initialize` : si le serveur visé est `filesystem-agent`, la capability `roots` est retirée à la volée du payload JSON-RPC envoyé au serveur MCP.
- Ajout de tests unitaires complets dans `tests/unit/test_mcp_bridge.py` validant que l'initialisation du `filesystem-agent` a bien ses `roots` de supprimées tandis que les autres serveurs (comme `shrimp-task-manager`) conservent la capability intacte.
- Exécution réussie des 25 tests unitaires du bridge.

### [2026-05-12 03:02:00] **Réécriture README.md root — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Réconcilier le README root (encore centré sur le Dashboard frontend obsolète) avec la nouvelle réalité architecturelle : Kimi Proxy = Pure Middleware MCP, passthrough session-less, et deprecation totale du frontend Dashboard.

**Actions réalisées** :
- Audit complet du README actuel : classification de chaque section en OBSOLETE / A_CONSERVER_MAIS_REFORMULER / A_AJOUTER.
- Réécriture totale selon `documentation/SKILL.md` : TL;DR first, Problem-First Opening, blocs ❌/✅, analogie unique (filtre à eau), trade-offs table, Golden Rule.
- Suppression de toutes les mentions du Dashboard frontend, WebSocket, jauges visuelles, sessions SQLite, métriques JS/CSS.
- Intégration des concepts MCP : Passthrough Session-Less, X-Target-Base-URL, MCP Tool Fixing, Context Sanitizer, Intelligent Compression.
- Mise à jour des métriques : 78 fichiers Python, 12 049 LOC, 61 routes API, 47 répertoires (pas de métriques frontend).
- Conservation du ton personnel et de la section "Pourquoi je partage ça".
- Section "Démarrage rapide" réécrite pour Cline (Base URL + X-Target-Base-URL) au lieu du navigateur.

**Conformité documentation/SKILL.md** :
- TL;DR ✔ (1 phrase bold en tête)
- Problem-First ✔ (la douleur du dev Cline avec différents providers)
- Blocs ❌/✅ ✔
- Analogie unique ✔ (filtre à eau, cohérente du début à la fin)
- Concepts nommés ✔ (Passthrough Session-Less, MCP Tool Fixing, etc.)
- Trade-offs table ✔ (direct vs session-based vs middleware)
- Golden Rule ✔ (transparence totale des transformations)
- French UI text ✔ (100% français)
- Pas de mention frontend/Dashboard ✔

### [2026-05-12 02:54:00] **Workflow Docs-Updater — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Synchroniser la documentation avec l'état actuel du code après l'architecture radicale et le pivot MCP-first.

**Audit structurel** :
- 78 fichiers Python, 12,049 LOC, 2,945 commentaires
- 61 endpoints API répartis sur 14 fichiers
- 93 opérations SQL (principalement `core/database.py`)
- 223 matches de configuration dans 36 fichiers

**Livrables** :
- `docs/features/compression.md` : Feature compression Phase 3 (endpoints `/api/compress/*`, configuration, trade-offs vs compaction, Golden Rule).
- `docs/features/sanitizer.md` : Feature sanitizer Phase 1 (masking automatique, récupération par hash, routing avancé, endpoints `/api/mask/*` et `/api/sanitizer/*`).
- `docs/proxy/passthrough.md` : Architecture radicale passthrough session-less (`/v1/chat/completions`, features MCP appliquées: tool fixing + observation masking + context pruning, fallback legacy).
- `docs/api/README.md` : Ajout route `POST /v1/chat/completions` (passthrough MCP session-less).
- `docs/README.md` : Features passthrough + MCP tool pruning ajoutées, version 2.0.5, date 2026-05-12.
- `docs/features/README.md` : Liens vers compression.md et sanitizer.md.

**Conformité documentation/SKILL.md** :
- TL;DR ✔ sur tous les nouveaux fichiers
- Problem-First ✔
- Blocs ❌/✅ ✔
- Trade-offs ✔
- Golden Rule ✔

**Manques identifiés mais non bloquants** :
- `docs/core/README.md` : métriques migrations obsolètes ("13 migrations" vs 59+ opérations SQL réelles).
- `docs/proxy/README.md` : date 2026-02-20, ne mentionne pas le passthrough.

### [2026-05-12 02:45:00] **Architecture radicale — Kimi Proxy = Pure Middleware MCP — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Transformer Kimi Proxy en middleware MCP universel, completement agnostique des providers. Cline controle totalement le provider, le modele et la cle API.

**Architecture** :
```
Cline → POST /v1/chat/completions
  Headers: X-Target-Base-URL + Authorization (cle API)
Kimi Proxy → Applique tool fixing + observation masking + pruning
  Forward vers X-Target-Base-URL/v1/chat/completions
Provider
```

**Livrables** :
- `proxy/passthrough.py` : `resolve_target()` utilise X-Target-Base-URL (radical) avec fallback legacy. `forward()` transmet la cle API du client (Authorization header).
- `api/routes/mcp_passthrough.py` : route POST /v1/chat/complements, docstring mise a jour.
- `config.toml.minimal` : ~80 lignes, uniquement configs MCP internes (sans [models], sans [providers], sans api_key).

**Validation** :
- Test RADICAL (X-Target-Base-URL) → cule atteinte, cle transmise, erreur 404 provider = preuve de connexion ✅
- Test LEGACY sans providers → 503 "Cible manquante" avec message explicite ✅
- Retro-compatibilite : config.toml original restaure, fallback legacy fonctionnel ✅

### [2026-05-12 02:20:00] **Endpoint /v1/chat/completions session-less MCP Passthrough — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Permettre a n'importe quel modele de transiter via le proxy sans session pre-configuree dans config.toml.

**Livrables** :
- `src/kimi_proxy/proxy/passthrough.py` : module core avec resolve_provider() (cascade header/body/split/default), PassthroughProcessor.apply_features() (tool fixing + observation masking schema1 + context pruning), et forward() (streaming/non-streaming avec injection cle API).
- `src/kimi_proxy/api/routes/mcp_passthrough.py` : route FastAPI POST /v1/chat/completions, independante de /chat/completions existante.
- `src/kimi_proxy/api/router.py` : integration du router mcp_passthrough.

**Validation** :
- `curl /v1/chat/completions` avec modele `nvidia/gpt-4.1` → provider resolu (nvidia), modele mappe (gpt-4.1), requete forwardee ✅
- `curl /chat/completions` existant fonctionne toujours ✅
- `pytest` MCP → **40 passed** ✅
- `py_compile` OK sur les deux nouveaux fichiers ✅

### [2026-05-12 02:05:00] **Pivot MCP-first de Kimi Proxy — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Recentrer Kimi Proxy sur ses features MCP en dépréciant le frontend Dashboard obsolète. L'utilisateur a migré vers Cline qui gère automatiquement la fenêtre de contexte.

**Tâches Shrimp** :
- T1 Audit et Inventaire Frontend vs MCP : ✅ TERMINÉ
- T2 Déprécier Routes UI dans main.py : ✅ TERMINÉ
- T3 Supprimer Assets Frontend Non-MCP : ✅ TERMINÉ
- T4 Vérifier Stabilité MCP Gateway et Healthchecks : ✅ TERMINÉ
- T5 Mettre à jour Documentation et Memory-Bank : ✅ TERMINÉ

**Livrables** :
- `src/kimi_proxy/main.py` : route `/` retourne JSON MCP (status opérationnel, service Kimi Proxy MCP, version 2.0.0-mcp). Mount `/static` et `/favicon.ico` retirés. Imports HTMLResponse/StaticFiles supprimés.
- `static/` : dossier entièrement supprimé (~370KB de fichiers frontend pur).
- Architecture 5 couches intacte (API <- Services <- Features <- Proxy <- Core).
- WebSocket manager conservé (broadcast générique backend).
- Routes `/api/*` et `/api/mcp-gateway/*` inchangées.

**Validation** :
- `curl /` → JSON MCP ✅
- `curl /health` → status ok ✅
- `curl /api/models` → 19 modèles ✅
- `pytest tests/unit/features/test_mcp_tool_pruning_engine.py test_mcp_gateway.py test_mcp_bridge.py -q` → **40 passed** ✅
- `create_app()` démarrage sans erreur ✅

### [2026-05-11 21:00:00] **Service systemd utilisateur pour Kimi Proxy Dashboard — TERMINÉ**
**Statut** : ✅ COMPLETÉ

**Objectif** : Permettre le démarrage automatique du Kimi Proxy Dashboard (incluant les serveurs MCP externes) au lancement de la session utilisateur Ubuntu via un service systemd user.

**Livrables** :
- Wrapper systemd : `scripts/start-systemd.sh`
  - Activation du venv, chargement de `.env`, démarrage des MCP (best-effort via `|| true`), lancement du dashboard en foreground avec `exec`.
  - Correction initiale : `PYTHONPATH=src exec python` invalide en bash → séparé en `export PYTHONPATH=src` puis `exec python -m kimi_proxy`.
- Unit systemd user : `~/.config/systemd/user/kimi-proxy.service`
  - `Type=simple`, `Restart=on-failure`, `RestartSec=5`.
  - `WantedBy=default.target` pour activation au démarrage de session.

**Validation** :
- `systemctl --user daemon-reload` OK.
- `systemctl --user enable kimi-proxy.service` OK (symlink créé).
- `systemctl --user start kimi-proxy.service` OK → **active (running)** (PID 228517, python).
- Healthcheck `curl http://localhost:8000/health` → réponse JSON OK.
- MCP démarrés conjointement (ports 8001/8003/8004/8005/8006).

**Invariants confirmés** :
- Aucune modification du code applicatif.
- Aucun secret en dur.
- Logs dirigés vers journal utilisateur (`journalctl --user -u kimi-proxy.service`).

### [2026-03-09 20:11:53] **MCP Tool Pruning — exclusion récursive des répertoires critiques TERMINÉE** : Implémentation d’un filtrage récursif excluant `.agents`, `.cline`, `.clinerules` et `.windsurf` du pruning dans `src/kimi_proxy/features/mcp_tool_pruning/engine.py`, avec détection request-first sur `params.arguments` puis response-aware best-effort sur les JSON textuels de `result.content[*].text`. Extension de configuration via `excluded_dirs` dans `config.toml` et `src/kimi_proxy/config/loader.py`, résolution runtime `KIMI_MCP_TOOL_PRUNING_EXCLUDED_DIRS` respectant `ENV > TOML > défaut interne`, et ajout de la métrique metadata-only `skipped_excluded_path` dans `src/kimi_proxy/features/mcp_tool_pruning/metrics.py`.

**Livrables** :
- `src/kimi_proxy/features/mcp_tool_pruning/engine.py` : helpers purs de normalisation/split/détection, skip pruning sur chemin exclu, conservation fail-open et JSON-RPC.
- `src/kimi_proxy/config/loader.py` : support TOML `excluded_dirs` avec parsing robuste.
- `src/kimi_proxy/features/mcp_tool_pruning/metrics.py` : compteur `skipped_excluded_path`.
- `config.toml` : fallback `excluded_dirs = [".agents", ".cline", ".clinerules", ".windsurf"]`.
- `tests/unit/features/test_mcp_tool_pruning_engine.py` : couverture request-side, traversal, Windows, response JSON, JSON malformé, env override.
- `tests/unit/features/test_mcp_gateway.py` et `tests/unit/test_mcp_bridge.py` : non-régression skip pruner + masking/relay inchangés.

**Validation** :
- `python3 -m pytest tests/unit/features/test_mcp_tool_pruning_engine.py tests/unit/features/test_mcp_gateway.py tests/unit/test_mcp_bridge.py -q` → **40 passed**.

**Invariants confirmés** :
- contrat JSON-RPC inchangé,
- fail-open conservé,
- ordre gateway prune-then-mask préservé,
- métriques strictement metadata-only,
- priorité `ENV > TOML` respectée.

### [2026-03-07 15:10:00] **Migration analytics Continue/Kimi + auto-session — TERMINÉ** : Finalisation de la migration multi-source Continue/Kimi. Livré: support `external_session_id` persisté dans `sessions`, décision auto-session corrélée par `provider` + `model` + `external_session_id` avec fallback historique, validation fail-open des artefacts Kimi (`context.jsonl`, `metadata.json`) documentée et testée, documentation FR mise à jour (`docs/features/auto-session.md`, `docs/features/log-watcher.md`). Validation: `python3 -m py_compile ...` OK + `python3 -m pytest tests/test_auto_session_model.py tests/unit/features/test_log_watcher_sources.py -q` = **17 passed**.

### [2026-03-02 00:25:31] **Clôture remédiations DeepInfra P1/P2/P3 — TERMINÉ** : Exécution complète du protocole Shrimp (plan_task/analyze/reflect/split/execute/verify) avec réflexion séquentielle avant T2/T3/T4. Livraisons validées: payload DeepInfra top-level (`query`/`documents`), durcissement `response_preview` (masqué hors debug, sanitizé/redacted/tronqué en debug), test anti-régression strict, documentation synchronisée. Validation finale: `./bin/kimi-proxy test ...` = **159 passed**. Invariants maintenus: contrat MCP JSON-RPC, fail-open, priorité `ENV > TOML`, aucun secret en dur. Aucune tâche active.

### [2026-03-01 23:18:00] **Workflow Docs-Updater Terminé** : Audit structurel complet (10528 LOC Python, 76 fichiers, 5 couches), mise à jour métriques API (61 routes), frontend (703 fonctions JS, 685 éléments HTML), base de données (59 opérations SQL). Documentation principale mise à jour avec métriques actuelles et nouvelles features (MCP Pruner DeepInfra, Log Watcher).

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

