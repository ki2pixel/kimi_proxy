# Audit du code mort et des fonctionnalités obsolètes

Date : 2026-11-06
Périmètre : `src/kimi_proxy/`, `scripts/`, `bin/`, `tests/`, configuration et documentation.
Mode : analyse statique, sans modification de production pendant la phase d'audit.

## TL;DR

Le middleware fonctionne, mais il porte deux architectures superposées. La première, session-less (`/v1/chat/completions`), est le chemin réellement utilisé par Cline et Continue. La seconde, orientée sessions, métriques, compaction et dashboard, est inerte en configuration livrée : aucune section `[providers]` ni `[models]` n'existe, donc `POST /chat/completions` retourne 503 pour toutes les requêtes. Le nettoyage peut supprimer environ 6 000 lignes de code mort sans toucher au contrat externe, à condition de traiter séparément la suppression assumée de `/chat/completions` et des routes UI orphelines.

Les cinq constats majeurs :

1. `POST /chat/completions` est une route legacy inerte ; elle n'a plus de provider configuré et duplique la logique de `/v1/chat/completions`.
2. Aucun endpoint WebSocket n'existe ; `services/websocket_manager.py` et ses 11 appels `broadcast()` sont des no-ops silencieux.
3. Les 11 routes `/api/compaction/*`, les 3 routes `/api/compress/*` et 6 routes de diagnostic/mémoire avancée n'ont aucun consommateur hors tests e2e ; le dashboard qui les utilisait a été supprimé.
4. Quatre tables SQLite sont totalement mortes et quatre autres ne sont jamais alimentées ; 8 des 14 migrations `ALTER TABLE` sont des no-ops.
5. La dépendance `websockets` est déclarée mais jamais importée ; `pydantic` et `tomli` sont importés sans être déclarés.

Baseline de tests : **237 tests passent** (`PYTHONPATH=src venv/bin/python -m pytest tests/ -q`).

## Méthode

L'audit combine quatre sources :

- Le graphe d'imports construit depuis `src/kimi_proxy/main.py` par `scripts/audit_dead_code.py`.
- L'inventaire AST des définitions et des décorateurs de routes.
- La recherche des tables SQL et de leurs usages (`CREATE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`).
- La comparaison des dépendances déclarées (`requirements.txt`, `setup.py`) avec les imports réels.

L'outil est volontairement autonome : il n'importe pas l'application, ne charge pas `config.toml` et n'écrit aucun fichier.

```bash
PYTHONPATH=src python scripts/audit_dead_code.py --format markdown
```

## Métriques

| Indicateur | Valeur |
| :--- | :--- |
| Modules Python analysés | 86 |
| Modules atteignables depuis `main.py` | 79 |
| Modules totalement orphelins | 1 (`proxy/mcp_gateway_rpc.py`) |
| Décorateurs de routes détectés | 44 |
| Routes montées | 41 (dont 1 route racine) |
| Routes définies mais non montées | 5 (`api/routes/memory.py`) |
| Tables SQL créées | 11 |
| Tables totalement mortes | 4 |
| Tables jamais alimentées | 2 (`memory_metrics`, `masked_content`) |
| Tests de référence | 237 passés |

Point important : « atteignable » ne signifie pas « utilisé ». `api/routes/memory.py` est importé par `api/routes/__init__.py` et `features/__init__.py` charge eageremment log_watcher, sanitizer, mcp et compression. Ces imports d'agrément rendent des modules visibles dans le graphe alors qu'aucun code ne les consomme.

## Matrice d'anomalies

Légende risque suppression : Nul / Faible / Moyen / Élevé. Sévérité : Critique / Haute / Moyenne / Faible.

| Composant / Fichier | Type | Preuve | Risque suppression | Sévérité / Gain | Décision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `api/routes/proxy.py` + `POST /chat/completions` | Route legacy inerte | `proxy.py:286-299` retourne 503 ; `config.toml` n'a ni `[providers]` ni `[models]` | Moyen (clients legacy) | Haute / ~700 LOC | Supprimer |
| `api/routes/compaction.py` + `features/compaction/` | 11 routes UI sans consommateur | `compaction.py:86-100` messages factices ; `183-188` hardcode `session_id == 140` | Moyen | Haute / ~1 500 LOC | Supprimer |
| `api/routes/compression.py` + `features/compression/` | 3 routes UI sans consommateur | `compression.py:69` ; compression sur `content_preview` tronqués | Moyen | Haute / ~600 LOC | Supprimer |
| `api/routes/memory.py` | 5 routes jamais montées + `MemoryService` + handlers WS | `memory.py:544-702` ; absent de `api/router.py` | Nul (jamais monté) | Haute / ~700 LOC | Supprimer |
| `services/websocket_manager.py` + 11 `broadcast` | Feature WS sans endpoint | `websocket_manager.py:16-42` ; aucun `@router.websocket` dans `src/` | Faible | Critique / ~90 LOC + 11 appels | Supprimer |
| `services/rate_limiter.py` | Jamais appliqué | `proxy.py:159-161` : `provider_key == "nvidia"` toujours faux | Faible | Moyenne / ~150 LOC | Supprimer |
| `services/alerts.py` | Jamais instancié | `alerts.py:9-170` | Faible | Moyenne / ~170 LOC | Supprimer |
| `core/auto_session.py` | Dormant | `auto_session.py:219-285` ; dépend de `[models]` absent | Faible | Haute / ~285 LOC | Supprimer |
| `proxy/mcp_gateway_rpc.py` | Stub sans import | `mcp_gateway_rpc.py:1-24` | Nul | Faible / 24 LOC | Supprimer |
| `features/sanitizer/masking.py` | `ContentMasker` sans appelant | `masking.py:11,172` | Faible | Moyenne / ~180 LOC | Supprimer |
| `features/sanitizer/routing.py` | Doublons sans appelant | `routing.py:10,47,150` | Faible | Moyenne / ~180 LOC | Supprimer |
| `features/mcp/analyzer.py` | Sans appelant | `analyzer.py:40` | Faible | Moyenne / ~100 LOC | Supprimer |
| `features/mcp/auto_memory.py` | Débranché | `auto_memory.py` ; `proxy.py:697-731` jamais appelé | Faible | Moyenne / ~250 LOC | Supprimer |
| `features/mcp/storage.py` | `memory_metrics` jamais écrite | `storage.py:10-143` | Faible | Moyenne / ~140 LOC | Remplacer par stats `mcp_memory_entries` |
| `core/database.py` | 8 fonctions mortes, 4 tables mortes, 8 migrations no-op | `database.py:711-1223` ; tables `providers`, `memory_segments`, `mcp_compression_results`, `mcp_routing_decisions` | Moyen (schéma) | Haute / ~900 LOC | Réduire sans `DROP` |
| `core/models.py` | 16 dataclasses mortes | `models.py:9-735` | Faible | Moyenne / ~500 LOC | Supprimer les mortes |
| `core/constants.py` / `core/exceptions.py` | 13 constantes et 5 exceptions sans usage | `constants.py:98-197` ; `exceptions.py:33-127` | Faible | Moyenne / ~100 LOC | Supprimer |
| `config/settings.py` | Module entier mort | `settings.py:1-110` | Faible | Moyenne / 110 LOC | Supprimer |
| `config/display.py` | Provider display/icon/color morts | `display.py:6-100` | Faible | Faible / ~70 LOC | Supprimer les mortes |
| `config/loader.py` | 5 fonctions mortes | `loader.py:45-222` | Faible | Moyenne / ~150 LOC | Supprimer |
| `proxy/router.py` | 4 fonctions mortes | `router.py:12-127` | Faible | Moyenne / ~150 LOC | Garder `get_provider_host_header` |
| `proxy/transformers.py` | 2 fonctions mortes | `transformers.py:77-158` | Faible | Faible / ~80 LOC | Supprimer |
| `proxy/stream.py` | Finalisation, usage, broadcast, buffer morts | `stream.py:83-231` ; `passthrough.py:412-419` passe `session_id=0` | Moyen (streaming) | Haute / ~250 LOC | Simplifier en relay SSE |
| `proxy/passthrough.py` | Fallback provider legacy et mapping morts | `passthrough.py:134-221` | Moyen (contrat) | Haute / ~90 LOC | Supprimer le legacy |
| `api/routes/mcp.py` | Mock `mem_001…005`, variable morte, routes avancées | `mcp.py:144,197-287,371-470` | Faible | Moyenne / ~200 LOC | Nettoyer et rewire stats |
| `api/routes/sanitizer.py` | Toggle no-op, config dupliquée | `sanitizer.py:18,68-100` | Faible | Moyenne / ~40 LOC | Supprimer le toggle |
| `main.py` | Sessions legacy, injection log watcher, docstring WebSocket | `main.py:3,275-277,305-306` | Faible | Moyenne / ~40 LOC | Nettoyer |
| `features/__init__.py`, `core/__init__.py`, `config/__init__.py` | Agrégateurs morts et imports eager | `features/__init__.py:6-20` | Faible | Faible / ~80 LOC | Simplifier |
| `bin/kimi-proxy` | `test` ignore ses arguments, fallback cassé | `bin/kimi-proxy:190-215` | Faible | Haute (DX) | Corriger |
| `bin/kimi-proxy-start`, `stop.sh` | Chemins cassés | `bin/kimi-proxy-start:5` ; `stop.sh:5` | Faible | Moyenne | Supprimer/corriger |
| `bin/build-css`, `scripts/config.js` | Résidus dashboard | fichiers cités | Nul | Faible | Supprimer |
| Tests fantômes | Imports de modules supprimés | `tests/mcp/*`, `tests/run_mcp_tests*`, `tests/unit/test-cline-polling.py` | Nul | Moyenne | Supprimer/porter |
| `requirements.txt` / `setup.py` | `websockets` inutile ; `pydantic`/`tomli` manquants | `requirements.txt:11` ; `setup.py:28-35` | Moyen (installation) | Haute | Corriger |
| `requirements-dev.txt` | `httpx` dupliqué, `mkdocs`/`memray` inutilisés | fichier cité | Faible | Faible | Nettoyer |
| `config.toml` | Sections/clés jamais lues, `[compaction]` obsolète | `config.toml:101-227` | Faible | Moyenne | Nettoyer |
| `config.toml.minimal` | Jamais lu, divergent | aucun lecteur | Faible | Moyenne | Supprimer |
| `docs/api/README.md` | Routes fantômes (WS, sessions, providers, export, cline) | `docs/api/README.md:17-52` | Faible | Moyenne | Réécrire |
| `.gitignore` | Caches et artefacts non ignorés | `.gitignore` | Faible | Moyenne | Compléter |
| `mcp_config.json` / `cline_mcp_settings.json` | Secrets inline, duplication | fichiers cités | Élevé (config IDE) | Critique (sécurité) | Documenter, hors nettoyage code |

## Preuves par catégorie

### 1. Routes et surface API

`api/router.py` monte 10 routeurs. `api/routes/memory.py` définit 5 routes sous `/api/memory` mais n'est jamais passé à `include_router`. Le fichier est importé par `api/routes/__init__.py:13` pour l'effet de bord, puis jamais consommé. Preuve : `api/router.py` ne contient que `sanitizer`, `mcp`, `compression`, `compaction`, `health`, `models`, `proxy`, `mcp_gateway`, `mcp_passthrough`.

`POST /chat/completions` est inatteignable en pratique. `main.py:275` crée une session uniquement si `providers` est non vide. `config.toml` ne contient aucune section `[providers]` ni `[models]`. `api/routes/proxy.py:286-299` retourne donc `503 Provider configuration missing` avant d'atteindre les 345 lignes de proxy, Gemini, streaming et gestion d'erreurs qui suivent.

Les routes UI orphelines sont identifiables par leurs seuls consommateurs : `tests/e2e/test_compaction_phase2.py` et les tests e2e historiques. Aucun script, aucune config MCP, aucun client du dépôt ne les appelle. Le dashboard qui les utilisait est déclaré déprécié dans `main.py:238-244` et `docs/README.md:6`.

### 2. WebSocket

Recherche exhaustive : aucun `@app.websocket`, aucun `@router.websocket`, aucun `add_websocket_route` dans `src/`. `services/websocket_manager.py` expose `ConnectionManager`, mais `connect()` n'est appelé nulle part. `active_connections` reste vide à vie, donc les 11 appels `await manager.broadcast(...)` sont des no-ops :

- `api/routes/proxy.py:446,485,579,712`
- `api/routes/compaction.py:131,315,523`
- `api/routes/compression.py:70`
- `features/compaction/storage.py:61`
- `core/auto_session.py:200-201`
- `api/routes/memory.py:292`

La dépendance `websockets>=11.0` est déclarée dans `requirements.txt:11` et `setup.py:38`, mais aucun `import websockets` n'existe. `uvicorn[standard]` tire déjà l'extra WebSocket de manière transitive.

### 3. Pipeline sessions, métriques et compaction

Le pipeline legacy est inerte par défaut :

- `config.toml` n'a ni `[providers]` ni `[models]`.
- `main.py:275` ne crée aucune session.
- `core/auto_session.py:219` retourne `(None, False)` dès que `detect_provider_from_model` échoue.
- `api/routes/proxy.py:231` retourne `None` immédiatement quand `session is None`.
- `api/routes/proxy.py:116-124` ne peut donc jamais alimenter `save_metric`, `get_auto_trigger()` ni `compaction_history`.

Les tables `providers`, `memory_segments`, `mcp_compression_results` et `mcp_routing_decisions` n'ont ni lecture ni écriture en dehors des `DELETE` de nettoyage. `memory_metrics` est lue par `/api/memory/stats` et `/api/sessions/{id}/memory`, mais `save_memory_metrics` n'est jamais appelée. `masked_content` est lue par `/api/mask*`, mais aucun `ContentMasker` ne l'alimente.

Huit migrations sur quatorze sont des no-ops : les colonnes existent déjà dans le `CREATE TABLE`. Elles sont masquées par `except sqlite3.OperationalError: pass`, ce qui rend le schéma non versionné et trompeur.

### 4. Duplications

| Duplication | Emplacements |
| :--- | :--- |
| Mapping de modèle | `proxy/router.py:130`, `passthrough.py:204`, `passthrough.py:365`, `auto_session.py:250` |
| `find_heavy_duty_model` | `proxy/router.py:58` et `features/sanitizer/routing.py:10` (copie exacte) |
| `get_session_total_tokens` | `features/sanitizer/routing.py:150` et `core/database.py:663` |
| `create_preview` | `sanitizer/masking.py:158` et `sanitizer/storage.py:77` |
| Listes de serveurs MCP | `api/routes/mcp.py:93` et `api/routes/mcp.py:444` |
| `GET memory/stats` | `api/routes/mcp.py:83` et `api/routes/memory.py:586` |
| Bloc headers provider | `api/routes/proxy.py:320-343` et `proxy/passthrough.py:337-361` |
| Bloc erreurs 429/401/413 | `api/routes/proxy.py:414-483` et `550-609` |
| Seuils d'alerte | `constants.py:170`, `alerts.py:83`, `alerts.py:124` (75/85/95 au lieu de 80/90/95) |
| Troncature head/tail | `features/mcp/gateway.py:122` et `features/mcp_tool_pruning/engine.py:615` |

### 5. Dépendances

| Dépendance | Constat |
| :--- | :--- |
| `websockets>=11.0` | Déclarée, jamais importée. À supprimer. |
| `uvicorn[standard]` | Tire l'extra WebSocket. Remplacer par `uvicorn` + `watchfiles` si `--reload` doit rester supporté. |
| `pydantic` | Importée par `api/routes/mcp.py:20`, non déclarée. Dépendance transitive de FastAPI. |
| `tomli>=2.0` | Fallback de `config/loader.py:91`, absent de `setup.py`. Une installation Python 3.10 via `pip install .` casse `load_config()`. |
| `numpy`, `sentence_transformers` | Imports optionnels de `features/mcp_pruner/local_rag.py`, non déclarés. Backend `local_rag` actif par défaut dans `config.toml:84`. |
| `mkdocs`, `memray` | Déclarés en dev, aucun `mkdocs.yml`, aucun script de profiling. |
| `httpx` | Déclaré deux fois (`requirements.txt` et `requirements-dev.txt`). |

## Décisions et justification userspace

Le contrat externe réel est limité à `/health`, `/models`, `/api/models`, `/v1/chat/completions`, `/api/mcp-gateway/{server}/rpc`, la surface mémoire conservée et les routes sanitizer en lecture. Les clients Cline et Continue passent par le bridge stdio et le gateway HTTP. Aucun client du dépôt n'appelle `/chat/completions`, `/api/compaction/*`, `/api/compress/*`, `/api/sessions/*`, `/api/providers`, `/api/export/*` ou `/api/cline/*`.

Décisions :

- Supprimer `POST /chat/completions` et le pipeline sessions/métriques associé. La route retourne déjà 503 en configuration livrée ; la suppression transforme un échec silencieux en 404 explicite.
- Supprimer immédiatement les routes UI orphelines, conformément à la décision validée.
- Conserver `/v1/chat/completions`, `/models`, `/api/models`, `/api/mcp-gateway/*`, `/health`.
- Conserver la surface mémoire `/api/memory/*` sauf `stats/advanced`, `all-servers` et `sessions/{id}/memory`.
- Conserver les routes sanitizer en lecture ; supprimer le toggle no-op.
- Conserver `scripts/mcp_bridge.py`, `scripts/start-mcp-servers.sh` et les serveurs MCP : ce sont les seuls chemins réellement utilisés par Cline.
- Conserver le log watcher et l'observation masking : features dormantes mais câblées et testées, activables par configuration.

## Risques résiduels hors périmètre

Ces constats ne sont pas du code mort et ne sont pas corrigés dans ce nettoyage :

- `proxy/tool_utils.py:455` journalise des arguments d'outils client en clair, avec un risque de fuite de secrets.
- `proxy/client.py:88-104` crée un `httpx.AsyncClient` par stream et ne le ferme pas sur le chemin nominal. Le relay SSE simplifié corrige ce point.
- `proxy/transformers.py` n'ajoute pas `?alt=sse` à `streamGenerateContent`, ce qui peut produire un tableau JSON au lieu de SSE avec Gemini.
- `api/routes/mcp_gateway.py` conserve un cache global process de 512 entrées et des circuit breakers globaux.
- `scripts/start-mcp-servers.sh` expose `MCP_ALLOWED_ROOT="/"` pour `fast-filesystem` et utilise `kill -9` sur les ports occupés.
- `mcp_config.json` et `cline_mcp_settings.json` contiennent des secrets inline, des chemins absolus et des blocs `env` dupliqués.

## Plan de nettoyage

Le détail exécutable est dans le plan approuvé. Les trois lots :

1. **Lot 1** : code orphelin autonome (modules sans import, symboles sans référence, agrégateurs morts), sans changement de comportement.
2. **Lot 2** : suppression des routes et features validées, réduction du schéma SQLite, simplification du streaming SSE et du passthrough, correction du conflit `Authorization` admin/provider.
3. **Lot 3** : dépendances, CLI, scripts, configuration, `.gitignore` et documentation.

## Vérification

```bash
python -m compileall -q src/kimi_proxy
PYTHONPATH=src venv/bin/python -m pytest tests/ -q
PYTHONPATH=src venv/bin/python -m ruff check src tests --select F821,F811,F401
./bin/kimi-proxy test
```

Smoke runtime :

```bash
curl -s http://127.0.0.1:8010/health
curl -s http://127.0.0.1:8010/models
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/ws
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8010/chat/completions
```

Attendu : `200` sur les routes conservées, `404` sur `/ws` et `/chat/completions`.

## État final après nettoyage

| Indicateur | Avant | Après |
| :--- | :--- | :--- |
| Modules Python de production | 86 | 63 |
| Modules orphelins | 1 + imports d'agrément | 1 placeholder (`services/`) |
| Routes applicatives montées | 41 | 19 |
| Tables SQL créées | 11 | 2 |
| Tests passés | 237 | 155 |

Les tests supprimés couvraient uniquement les routes et features retirées (compaction, compression, sessions, WebSocket, rate limiting). Les scénarios critiques d'observation masking et de context pruning ont été portés vers `/v1/chat/completions`.

Symboles restants sans référence runtime : `count_tokens_tiktoken`, `parse_token_metrics`, `COMPILE_CHAT_END`, `prune_text_with_deepinfra`, `prune_text_with_local_rag` et les dataclasses de `mcp_pruner/spec.py`. Ils sont conservés comme API publique, contrats de test ou points d'extension, pas comme code mort.

## Golden Rule

Une route sans consommateur n'est pas un contrat ; c'est une dette. Une feature désactivée par défaut n'est pas morte si elle est câblée et testée ; elle est dormante. Le nettoyage doit supprimer la première et préserver la seconde.
