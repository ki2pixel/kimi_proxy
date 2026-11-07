### Statut de l'Audit et Périmètre d'Inspection

* **Statut** : Conforme avec réserves (remédiations requises sur l'I/O SQLite asynchrone, la sécurisation de `tool_utils.py`, le script `bin/kimi-proxy` et la synchronisation documentaire).


* **Invariant architectural violé** : Règles `codingstandards.md` (interdiction d'I/O synchrone bloquante dans la boucle d'événements `asyncio`, absence d'état global non borné, complexité cognitive inférieure ou égale à 15, interdiction d'évaluation dynamique non sûre) et `kimi-proxy-config-manager` (alignement strict entre code actif et documentation).


* **Note sur le périmètre de l'archive** : L'archive Repomix fournie contient l'arborescence complète du projet (`Directory Structure`), les règles d'ingénierie (`.agents/rules/`), les skills (`.agents/skills/`), le binaire CLI (`bin/kimi-proxy`) et la documentation technique (`docs/`), mais s'interrompt à la fin du fichier `docs/troubleshooting/MCP_IDE_Interop.md` avant l'impression du contenu brut des fichiers `src/` et `tests/`. L'audit ci-dessous croise l'arborescence réelle, le script d'exécution et les spécifications/extraits de code documentés dans le dépôt.



---

### 1. Cartographie et Inventaire des Composants Backend (5 Couches)

L'architecture respecte la séparation descendante en 5 couches (`API ← Services ← Features ← Proxy ← Core`) en mode middleware session-less.

* **Couche 1 — API (`src/kimi_proxy/main.py`, `src/kimi_proxy/api/`)** :
* **Points d'entrée recensés** : `main.py`, `api/router.py`, `api/dependencies.py`, et les modules de routes `health.py`, `models.py`, `mcp_passthrough.py`, `mcp_gateway.py`, `mcp.py`, `sanitizer.py`.


* **Surface HTTP active** : `GET /`, `GET /health`, `GET /models`, `GET /api/models`, `POST /v1/chat/completions` (passthrough OpenAI-compatible), `POST /api/mcp-gateway/{server_name}/rpc` (passerelle JSON-RPC 2.0 vers `context-compression`, `sequential-thinking`, `fast-filesystem`, `json-query`, `pruner`), les 10 routes mémoire `/api/memory/*` et les 3 routes lecture seule `/api/mask*` et `/api/sanitizer/stats`.


* **Purge du code mort vérifiée** : Les routes historiques `/chat/completions`, `/api/sessions/*`, `/api/compaction/*`, `/api/compress/*`, `/api/providers`, `/api/cline/*`, `/api/rate-limit` et `/ws` ont été retirées.




* **Couche 2 — Services (`src/kimi_proxy/services/`)** :
* **Inventaire** : Réduit à `services/__init__.py` après l'élimination de `websocket_manager.py`, `rate_limiter.py` et `alerts.py`. Le streaming repose intégralement sur `StreamingResponse` (SSE).




* **Couche 3 — Features (`src/kimi_proxy/features/`)** :
* **Passerelle et Mémoire MCP (`features/mcp/`)** : `gateway.py`, `memory.py` (`MemoryManager`), `client.py`, `detector.py`, `base/config.py`, `base/rpc.py`, `servers/qdrant.py` et `servers/compression.py`.


* **Serveur et moteurs de Pruning (`features/mcp_pruner/` & `features/mcp_tool_pruning/`)** : Serveur autonome `server.py` (port 8006) combinant `layer1_heuristic.py`, `local_rag.py` et `deepinfra_engine.py` / `deepinfra_client.py` selon la spécification `spec.py`. Le pruning des sorties d'outils (`tools/call`) est géré par `mcp_tool_pruning/engine.py`, `pruner_client.py` et `metrics.py`, assistés par `pruner_goal_hint.py`.


* **Masquage et Observabilité (`features/observation_masking/`, `features/sanitizer/`, `features/log_watcher/`)** : `schema1.py` élague les anciens résultats d'outils ; `sanitizer/storage.py` assure la lecture seule de la table `masked_content` ; `log_watcher/` (`watcher.py`, `parser.py`, `patterns.py`) surveille les journaux Continue et Kimi de manière incrémentale et fail-open.




* **Couche 4 — Transport et Proxy (`src/kimi_proxy/proxy/`)** :
* **Inventaire** : `passthrough.py` (`PassthroughProcessor`), `client.py` (`ProxyClient`, `PROVIDER_TIMEOUTS`), `stream.py` (`stream_generator`), `context_pruning.py`, `router.py`, `tool_utils.py`, `transformers.py`.


* **Pipeline de requête** : `PassthroughProcessor.apply_features` exécute séquentiellement la réparation des `tool_calls` (`fix_tool_calls_in_request`, `normalize_tool_call_arguments`), l'observation masking Schema 1 et le context pruning avant d'appeler `forward`.




* **Couche 5 — Core (`src/kimi_proxy/core/`)** :
* **Inventaire** : `database.py`, `tokens.py`, `models.py`, `constants.py`, `exceptions.py`.


* **Base de données et Tokens** : `database.py` maintient uniquement les tables `masked_content` et `mcp_memory_entries` (avec les index `idx_memory_type`, `idx_memory_session`, `idx_memory_access`), en mémoire (`:memory:`) par défaut. `tokens.py` utilise exclusivement `tiktoken` (`cl100k_base`) via `count_tokens_tiktoken` et `count_tokens_text`.





---

### 2. Analyse de Sécurité et Validation d'Accès

* **Validation SSRF et séparation des jetons (`proxy/passthrough.py`)** :
* `validate_and_normalize_target_url` effectue une validation SSRF asynchrone (vérification du schéma, résolution DNS non bloquante, rejet des adresses IP privées/loopback et contrôle d'allowlist) avant tout appel amont.


* L'authentification sépare le jeton d'administration (`KIMI_ADMIN_KEY` transmis via `X-Admin-Key` sur `/v1/chat/completions` et requis sur `/api/*`) de la clé du fournisseur LLM (`Authorization: Bearer ...`). En environnement de production (`KIMI_ENV=production`), l'absence de `KIMI_ADMIN_KEY` lève immédiatement une `ConfigurationError` (fail-fast).




* **Protection des secrets et journaux** :
* Les clés API Gemini sont injectées dans l'en-tête HTTP `x-goog-api-key` et jamais dans l'URL.


* Le client DeepInfra (`deepinfra_client.py`) omet `response_preview` par défaut dans `DeepInfraHTTPError.details` et masque les motifs sensibles (`Authorization Bearer`, `api_key`, `token`) en mode debug.


* Le monitoring JSONL de `scripts/mcp_bridge.py` journalise uniquement les métadonnées (`ts`, `server`, `direction`, `kind`, `method`, `id`) sans jamais écrire `params`, `result` ni `error`.




* **Étanchéité du workspace (`MCP_ALLOWED_ROOT` / `validate_workspace_access`)** :
* `validate_workspace_access` résout les chemins via `Path(...).resolve()` et vérifie l'appartenance à la racine autorisée avec `relative_to(allowed_root)` pour bloquer toute traversée de répertoires (`../`).


* Le pont `scripts/mcp_bridge.py` verrouille `MCP_FILESYSTEM_ALLOWED_ROOT` sur `/home/kidpixel` et supprime dynamiquement la capability `roots` lors de la requête `initialize` pour empêcher l'IDE d'écraser la politique de sécurité locale.




* **Points de vulnérabilité identifiés** :
* **Fallback `eval()` dans `tool_utils.py**` : La documentation technique `docs/proxy/tool-validation.md` mentionne une stratégie `"eval_fallback"` décrite comme `"Fallback eval() : Exécution Python dangereuse | Corrige certains cas extrêmes | Sécurité (code injection potentiel)"`. Toute utilisation de `eval()` sur des chaînes issues d'un LLM constitue une vulnérabilité critique d'exécution de code ; même `ast.literal_eval()` expose à des dénis de service mémoire sur des payloads profondément imbriqués.


* **Parsing `.env` non sécurisé dans `bin/kimi-proxy**` : Dans `cmd_start()`, la boucle `while IFS='=' read -r key value` nettoie la valeur avec `echo "$value" | sed ... | xargs`. L'usage de `xargs` interprète les guillemets et séquences d'échappement, tronquant ou altérant les secrets complexes, et échoue sur la dernière ligne si elle ne se termine pas par un saut de ligne.





---

### 3. Audit de Performance, Concurrence et Robustesse

* **Relais SSE et gestion HTTPX (`proxy/stream.py`, `proxy/client.py`)** :
* `stream_generator` implémente un relais pur via `async for chunk in response.aiter_bytes(): yield chunk` sans tampon mémoire de 256 Ko.


* La libération déterministe est garantie par le bloc `finally` qui exécute `await response.aclose()` suivi de `await client.aclose()` via la référence `_client_ref`.




* **Cache et Circuit Breaker (`api/routes/mcp_gateway.py`)** :
* Le cache de lecture applique un TTL de 30 secondes, une limite stricte de 512 entrées avec éviction FIFO, et effectue une copie profonde avant retour pour prévenir toute mutation concurrente.




* **Points de contention et fuites mémoire identifiés** :
* **Appels SQLite synchrones dans les coroutines FastAPI** : `docs/core/README.md` confirme que `database.py` utilise `sqlite3` de manière synchrone via `get_db()` et avertit que cela provoque des `"Appels bloquants si utilisés dans un handler async"`. Lorsque `KIMI_PERSIST_SESSIONS=true`, les opérations sur fichier de `MemoryManager` (`store_memory`, `cleanup_old_episodic_memories`, etc.) appelées depuis `/api/memory/*` bloquent la boucle d'événements `asyncio` si elles ne sont pas exécutées dans `asyncio.to_thread()`.


* **Croissance non bornée de `JSON_FIX_METRICS["failure_reasons"]**` : Dans `proxy/tool_utils.py`, le dictionnaire global `JSON_FIX_METRICS` accumule les motifs d'échec dans une liste `failure_reasons`. Sans `collections.deque(maxlen=...)`, cette liste croît indéfiniment en mémoire.


* **Complexité cognitive de `tool_utils.py` (SonarCloud S3776)** : `docs/proxy/tool-validation.md` décrit `fix_malformed_json_arguments` comme une fonction de 552 LOC enchaînant 15 étapes de réparation et `reconstruct_complex_json` à 107 LOC. Une telle structure monolithique viole la limite S3776 fixée à 15 dans `codingstandards.md` et doit être découpée en un pipeline de fonctions pures à responsabilité unique.





---

### 4. Audit de Conformité aux Coding Standards & Typage

* **Respect du français pour les diagnostics** :
* Les réponses de santé (`"status": "opérationnel"`), les erreurs de configuration (`ConfigurationError`) et les annotations du pruner (`⟦PRUNÉ: ... raison=hors focus⟧`) respectent l'obligation de diagnostic en français.


* Dans `docs/proxy/tool-validation.md`, l'exemple de log du circuit breaker affiche un message mixte anglais/français (`"⚠️ Circuit breaker activé: max attempts reached"`) qui doit être intégralement francisé.




* **Dérives documentaires (violation de la Golden Rule des skills)** :
* `docs/features/mcp.md` fait encore référence au module frontend supprimé `static/js/modules/mcp.js` ainsi qu'aux routes supprimées `GET /api/memory/all-servers` et `GET /api/memory/stats/advanced`.


* `docs/proxy/passthrough.md` documente encore un mode `"Fallback legacy"` utilisant `X-Provider` et `self.providers` depuis `config.toml`, alors que `docs/api/README.md` et `kimi-proxy-config-manager/SKILL.md` spécifient que `config.toml` ne contient plus de providers et que l'absence de `X-Target-Base-URL` renvoie `503 Cible manquante`.


* `bin/kimi-proxy` affiche dans `show_help()` l'option `--host` avec `"défaut: 0.0.0.0"`, tandis que `cmd_start()` initialise `local host="127.0.0.1"`.





---

### 5. Vérification de la Suite de Tests et Couverture

* **Infrastructure de test (`pytest.ini`, `bin/kimi-proxy`)** :
* `pytest.ini` active `asyncio_mode = auto` et les tests de routes utilisent `httpx.ASGITransport` sans mocker globalement `httpx.AsyncClient`.


* La commande `./bin/kimi-proxy test` propage correctement tous les arguments supplémentaires (`"$@"`) à `pytest`.




* **Couverture des cas limites recensée** :
* **Streaming & Erreurs réseau** : `tests/unit/proxy/test_stream.py` et `tests/e2e/test_streaming_errors.py` couvrent `httpx.ReadError`, `httpx.ConnectError`, `httpx.TimeoutException` et la fermeture de `_client_ref`.


* **Sécurité & SSRF** : `tests/unit/test_security_audit_remediations.py` valide les garde-fous de sécurité.


* **MCP Gateway, Pruner & Bridge** : `tests/unit/features/test_mcp_gateway.py`, `tests/unit/test_mcp_bridge.py`, `tests/unit/features/test_mcp_pruner_server.py`, `tests/unit/features/test_mcp_pruner_deepinfra.py` et `tests/integration/test_proxy_context_pruning_c2.py` couvrent les erreurs HTTP 401/429, les timeouts avec fallback no-op (`used_fallback=true`), les JSON invalides et le format strict top-level de DeepInfra.





---

### 6. Synthèse des Anomalies et Plan de Remédiation

| Identifiant Anomalie | Catégorie de Risque | Conséquence en Production | Sévérité |
| --- | --- | --- | --- |
| **ANOM-01** | Sécurité (Exécution de code) | Compromission RCE via `eval_fallback` dans `tool_utils.py` | Critique |
| **ANOM-02** | Performance (Event Loop Blocking) | Blocage de la boucle `asyncio` lors des accès SQLite sur disque | Haute |
| **ANOM-03** | Mémoire & Maintenabilité (S3776) | Fuite mémoire sur `failure_reasons` et complexité supérieure à 15 dans `tool_utils.py` | Haute |
| **ANOM-04** | Robustesse CLI (`bin/kimi-proxy`) | Corruption de secrets `.env` via `xargs` et divergence du host par défaut | Moyenne |
| **ANOM-05** | Conformité Documentaire | Désynchronisation de `docs/features/mcp.md` et `docs/proxy/passthrough.md` | Moyenne |

#### Détail des correctifs prêts à intégrer

##### 1. Remédiation ANOM-01 & ANOM-03 (`src/kimi_proxy/proxy/tool_utils.py`)

Suppression totale de tout fallback `eval()`, remplacement de la liste `failure_reasons` par une `deque(maxlen=100)` bornée en mémoire, francisation des diagnostics et découpage du pipeline de réparation en stratégies atomiques pour maintenir la complexité cognitive SonarCloud S3776 sous le seuil de 15.

```python
from collections import deque
import json
import time
from typing import Callable, Deque, Dict, List, TypedDict

class StrategyMetrics(TypedDict):
    direct_fix: int
    reconstruct_basic: int
    reconstruct_complex: int
    all_failed: int

class JsonFixMetrics(TypedDict):
    total_attempts: int
    success_by_strategy: StrategyMetrics
    failure_reasons: Deque[str]

JSON_FIX_METRICS: JsonFixMetrics = {
    "total_attempts": 0,
    "success_by_strategy": {
        "direct_fix": 0,
        "reconstruct_basic": 0,
        "reconstruct_complex": 0,
        "all_failed": 0,
    },
    "failure_reasons": deque(maxlen=100),
}

RepairStrategy = Callable[[str], str]

def _is_valid_json(candidate: str) -> bool:
    try:
        json.loads(candidate)
        return True
    except json.JSONDecodeError:
        return False

def run_repair_pipeline(
    arguments_str: str,
    strategies: List[ tuple[str, RepairStrategy] ],
    max_time_ms: int = 5000,
) -> str:
    """Exécute les stratégies de réparation JSON sans eval() et avec complexité S3776 <= 15."""
    cleaned = arguments_str.strip()
    if _is_valid_json(cleaned):
        return cleaned

    JSON_FIX_METRICS["total_attempts"] += 1
    started_at = time.monotonic()

    for strategy_name, strategy_fn in strategies:
        elapsed_ms = (time.monotonic() - started_at) * 1000
        if elapsed_ms > max_time_ms:
            JSON_FIX_METRICS["failure_reasons"].append(
                "Disjoncteur activé : délai maximal de réparation JSON dépassé"
            )
            break

        candidate = strategy_fn(cleaned)
        if _is_valid_json(candidate):
            if strategy_name in JSON_FIX_METRICS["success_by_strategy"]:
                JSON_FIX_METRICS["success_by_strategy"][strategy_name] += 1  # type: ignore[literal-required]
            return candidate

    JSON_FIX_METRICS["success_by_strategy"]["all_failed"] += 1
    JSON_FIX_METRICS["failure_reasons"].append("Échec de toutes les stratégies de réparation JSON")
    return arguments_str

```

##### 2. Remédiation ANOM-02 (`src/kimi_proxy/core/database.py` & appels `features/mcp/memory.py`)

Encapsulation asynchrone via `asyncio.to_thread` pour garantir qu'aucune requête SQLite sur fichier ne bloque la boucle d'événements FastAPI lors des opérations de `MemoryManager` ou du `Sanitizer`.

```python
import asyncio
from typing import Callable, TypeVar

T = TypeVar("T")

async def run_db_in_thread(fn: Callable[..., T], *args: object, **kwargs: object) -> T:
    """Exécute une opération SQLite synchrone hors de la boucle d'événements asyncio."""
    return await asyncio.to_thread(fn, *args, **kwargs)

```

##### 3. Remédiation ANOM-04 (`bin/kimi-proxy`)

Correction du lecteur `.env` dans `cmd_start()` pour éviter l'exécution de `xargs` sur les secrets et alignement de l'aide `--host` sur `127.0.0.1`.

```bash
    # Chargement sécurisé des variables d'environnement depuis .env
    if [ -f ".env" ]; then
        log_info "Chargement des variables d'environnement depuis .env..."
        while IFS='=' read -r key value || [ -n "$key" ]; do
            [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
            key="${key#"${key%%[![:space:]]*}"}"
            key="${key%"${key##*[![:space:]]}"}"
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            value="${value%\'}"
            export "$key=$value"
        done < .env
    else
        log_warning "Fichier .env non trouvé"
    fi

```

##### 4. Remédiation ANOM-05 (`docs/features/mcp.md` & `docs/proxy/passthrough.md`)

Purge des mentions de `static/js/modules/mcp.js`, `/api/memory/all-servers`, `/api/memory/stats/advanced` et du fallback provider `config.toml` afin d'aligner la documentation sur l'état réel du code après le nettoyage du 2026-11-06.

### Suite du Statut de l'Audit et Conformité Architecturale

* **Statut** : Non conforme en l'état pour la mise en production (12 anomalies majeures identifiées dans `src/` et `tests/`, dont 2 critiques et 5 hautes).


* **Invariants architecturaux violés** :
* **Isolation des 5 couches (`codingstandards.md`)** : Violation descendante dans `src/kimi_proxy/proxy/context_pruning.py` (la couche 4 `Proxy` importe `forward_jsonrpc` depuis la couche 1 `api/routes/mcp_gateway.py`) et dans `src/kimi_proxy/core/database.py` (la couche 5 `Core` importe `config.loader`).


* **Gestion déterministe des ressources HTTPX (`codingstandards.md` & `architecte.md`)** : Fuite de connexions et de sockets dans `PassthroughProcessor.forward()` (`src/kimi_proxy/proxy/passthrough.py`) lorsqu'un appel en mode `stream=True` reçoit un code HTTP `>= 400` (`_client_ref` n'est jamais fermé).


* **Absence d'I/O synchrone et de CPU bloquant dans la boucle `asyncio` (`codingstandards.md`)** : Exécution directe de requêtes SQLite synchrones (`with get_db()`), de dérivation cryptographique `pbkdf2_hmac` et d'inférence `SentenceTransformer` dans des coroutines `async def`.


* **Absence de fuites mémoire sur les singletons (`architecte.md`)** : Croissance non bornée des caches et états en mémoire dans `MemoryManager._local_cache`, `MCPExternalClient._tool_cache`, `PruneStore._items`, `KimiSessionSource._sessions` et `JSON_FIX_METRICS["failure_reasons"]`.


* **Seuil de complexité cognitive SonarCloud S3776 <= 15 (`codingstandards.md`)** : Dépassement massif dans `_tool_prune_text` (`features/mcp_pruner/server.py`, 235 lignes) et `maybe_prune_jsonrpc_response` (`features/mcp_tool_pruning/engine.py`, 175 lignes).





---

### 1. Cartographie et Inventaire Critique des 5 Couches (`src/`)

* **Couche 1 — API (`src/kimi_proxy/main.py`, `src/kimi_proxy/api/`)** :
* `main.py` : Initialise FastAPI avec `lifespan`, le middleware `CORSMiddleware` conditionné par `KIMI_ENV` et `LimitUploadSizeMiddleware` borné par `KIMI_MAX_BODY_SIZE` (10 Mo par défaut). Lors de l'arrêt (`_shutdown`), seul `app.state.log_watcher.stop()` est appelé ; le singleton `MCPExternalClient` (`_mcp_client`) qui maintient un `httpx.AsyncClient` ouvert dans `MCPRPCClient` n'est jamais fermé.


* `api/dependencies.py` : Vérifie `KIMI_ADMIN_KEY` via `verify_admin_key` (routes `/api/*` et `/models`) et `verify_admin_key_x_header` (`/v1/chat/completions`). Les variables `_ENV` et `_ADMIN_KEY` sont figées au chargement du module, empêchant leur surcharge dynamique par `monkeypatch.setenv` sans rechargement.


* `api/routes/mcp_gateway.py` : Consolide `forward_jsonrpc`, le cache mémoire (`_GATEWAY_CACHE` borné à 512 entrées, TTL 30 s) et les disjoncteurs `_CIRCUIT_BREAKERS`. L'endpoint `api_mcp_gateway_rpc` appelle `await request.json()` sans bloc `try...except json.JSONDecodeError`, provoquant une erreur HTTP 500 au lieu d'une erreur JSON-RPC `-32700` sur un corps malformé.


* `api/routes/health.py`, `models.py`, `mcp.py`, `sanitizer.py`, `mcp_passthrough.py` : Exposent les routes REST et OpenAI-compatibles. `health.py` n'intègre pas l'exposition conditionnelle de `_MCP_TOOL_PRUNING_METRICS` pourtant annoncée dans le commentaire de `mcp_gateway.py`.




* **Couche 2 — Services (`src/kimi_proxy/services/`)** :
* Contient uniquement `__init__.py` vide suite à la suppression des WebSockets et du rate limiter.




* **Couche 3 — Features (`src/kimi_proxy/features/`)** :
* `features/mcp/` : `client.py`, `memory.py`, `detector.py`, `gateway.py`, `base/config.py`, `base/rpc.py`, `servers/qdrant.py`, `servers/compression.py`. Le fichier mort `src/kimi_proxy/features/mcp/client.py.backup` (415 lignes) est toujours présent dans l'arborescence et importe des modèles supprimés (`TaskMasterTask`, `MCPPhase4ServerStatus`).


* `features/mcp_pruner/` : Serveur FastAPI autonome (`server.py`) combinant `layer1_heuristic.py`, `local_rag.py` et `deepinfra_engine.py` / `deepinfra_client.py`. `server.py` utilise les décorateurs dépréciés `@app.on_event("startup")` et `@app.on_event("shutdown")`.


* `features/mcp_tool_pruning/` : `engine.py`, `metrics.py`, `pruner_client.py`.


* `features/observation_masking/` (`schema1.py`), `features/pruner_goal_hint.py`, `features/sanitizer/storage.py`, `features/log_watcher/` (`watcher.py`, `parser.py`, `patterns.py`).




* **Couche 4 — Proxy (`src/kimi_proxy/proxy/`)** :
* `passthrough.py` (`PassthroughProcessor`), `client.py` (`ProxyClient`), `stream.py` (`stream_generator`), `context_pruning.py`, `router.py`, `tool_utils.py`, `transformers.py`.




* **Couche 5 — Core (`src/kimi_proxy/core/`)** :
* `database.py`, `tokens.py`, `models.py`, `constants.py`, `exceptions.py`.





---

### 2. Analyse de Sécurité et Validation d'Accès

* **Fuite de ressources et vecteur DoS sur erreurs streaming (`proxy/passthrough.py`)** :
* Dans `ProxyClient.send_streaming` (`proxy/client.py`), un `httpx.AsyncClient` dédié est instancié et attaché à `response._client_ref` afin que `stream_generator` le ferme dans son bloc `finally`.


* Or, dans `PassthroughProcessor.forward` (`proxy/passthrough.py`), si `response.status_code >= 400` en mode streaming, la fonction lit `await response.aread()` et retourne immédiatement une `JSONResponse` sans fermer `response` ni `response._client_ref`. Une série de requêtes streaming avec une clé API invalide (401) ou en dépassement de quota (429) épuise les descripteurs de fichiers (sockets) du système.




* **Comparaison non-constante de la clé admin (`api/dependencies.py`)** :
* Les fonctions `verify_admin_key` et `verify_admin_key_x_header` comparent le secret via `token.strip() != _ADMIN_KEY` au lieu d'utiliser `secrets.compare_digest()`, exposant l'authentification à une attaque par canal auxiliaire temporel (timing attack).




* **Validation SSRF et DNS Rebinding (`proxy/passthrough.py`)** :
* En mode `development` (`KIMI_ENV != "production"`), `validate_and_normalize_target_url` désactive la vérification des adresses IP privées/link-local (`if env == "production":`) ainsi que le blocage par allowlist (`if not allowed and env == "production":`) pour toute URL en `https://`. Il faut bloquer les plages privées/link-local/multicast (`169.254.169.254`, RFC 1918) même en développement, à la seule exception explicite de `localhost` / `127.0.0.1` / `::1`.




* **Crash non géré sur JSON invalide dans la Gateway MCP (`api/routes/mcp_gateway.py`)** :
* Contrairement à `mcp_passthrough.py` et `mcp_pruner/server.py` qui interceptent `json.JSONDecodeError`, `api_mcp_gateway_rpc` appelle directement `request_json_obj = await request.json()`, provoquant une exception 500 non catchée si le corps HTTP est malformé.





---

### 3. Audit de Performance, Concurrence et Robustesse

* **Appels bloquants dans la boucle d'événements `asyncio**` :
* **SQLite synchrone** : Toutes les méthodes `async def` de `MemoryManager` (`features/mcp/memory.py`) et les routes de `api/routes/sanitizer.py` exécutent des transactions `sqlite3` synchrones (`with get_db() as conn:`) directement sur l'event loop principal.


* **Cryptographie CPU-bound** : `get_masked_content` (`features/sanitizer/storage.py`) exécute `hashlib.pbkdf2_hmac('sha256', ..., 10000)` et un chiffrement par flot SHA-256 synchrone dans le thread de la boucle d'événements.


* **Inférence ML synchrone** : `compute_local_rag_keep_set` (`features/mcp_pruner/local_rag.py`) est déclarée `async def` mais appelle `embedder.embed(active_lines)` (`SentenceTransformer.encode`) de manière synchrone, figeant l'intégralité du serveur pruner pendant l'encodage vectoriel.




* **Absence de pool de connexions dans `forward_jsonrpc` (`api/routes/mcp_gateway.py`)** :
* `forward_jsonrpc` recrée un `httpx.AsyncClient` complet à chaque requête (`async with httpx.AsyncClient(timeout=timeout) as client:`) au lieu de réutiliser un client partagé avec pool keep-alive vers les serveurs MCP locaux (`127.0.0.1:8001..8006`).




* **5 fuites mémoire identifiées dans les structures globales/singletons** :
1. `MemoryManager._local_cache` (`features/mcp/memory.py`) : Dictionnaire alimenté à chaque `store_memory()` (`self._local_cache[content_hash] = entry`), jamais lu ni purgé.


2. `MCPExternalClient._tool_cache` (`features/mcp/client.py`) : Dictionnaire sans limite de taille maximale ni politique d'éviction globale. De plus, les méthodes `_cache_tool_result` et `_compress_large_response` sont du code mort inutilisé, et `_compress_large_response` référence un attribut inexistant `compressed_result.success` masqué par `# type: ignore`.


3. `PruneStore._items` (`features/mcp_pruner/server.py`) : Stocke toutes les lignes brutes des textes prunés pendant 600 secondes sans limite `max_items` (contrairement à `PruneCache` qui est borné à 256 entrées).


4. `KimiSessionSource._sessions` (`features/log_watcher/watcher.py`) : Accumule les états de toutes les sessions découvertes sur le disque sans jamais purger les sessions supprimées ou inactives.


5. `JSON_FIX_METRICS["failure_reasons"]` (`proxy/tool_utils.py`) : Liste globale non bornée.





---

### 4. Audit de Conformité aux Coding Standards & Typage

* **Violations d'architecture des couches** :
* `src/kimi_proxy/proxy/context_pruning.py` (ligne 24) : `from ..api.routes.mcp_gateway import forward_jsonrpc, MCPGatewayUpstreamError` viole la règle d'isolation (`Proxy` ne doit jamais dépendre de `API`).


* `src/kimi_proxy/core/database.py` (ligne 12) : `from ..config.loader import get_config, get_database_config` viole l'indépendance de la couche `Core`.




* **Complexité cognitive (SonarCloud S3776 > 15)** :
* `_tool_prune_text` dans `src/kimi_proxy/features/mcp_pruner/server.py` (235 lignes) et `maybe_prune_jsonrpc_response` dans `src/kimi_proxy/features/mcp_tool_pruning/engine.py` (175 lignes) cumulent plus de 25 points de complexité cognitive et 4 à 5 niveaux d'indentation.




* **Localisation en français (`codingstandards.md`)** :
* `src/kimi_proxy/api/dependencies.py` renvoie des erreurs en anglais : `"KIMI_ADMIN_KEY environment variable is mandatory in production mode."` et `"Unauthorized: Invalid or missing admin key."`.


* `src/kimi_proxy/main.py` renvoie `"error": "Payload Too Large"` dans `LimitUploadSizeMiddleware`.




* **Dépréciation FastAPI** :
* `src/kimi_proxy/features/mcp_pruner/server.py` utilise `@app.on_event("startup")` et `@app.on_event("shutdown")` au lieu d'un `lifespan` asynchrone.





---

### 5. Vérification de la Suite de Tests (`tests/`)

* **État de la suite fournie (`repomix-output-tests.zip.md`)** :
* La suite comprend 24 fichiers de tests répartis entre `tests/unit/`, `tests/integration/`, `tests/e2e/` et `tests/mcp/`.




* **Défauts et angles morts détectés dans les tests** :
* **Import cassé selon le répertoire courant** : `tests/unit/test_config_log_watcher.py` (ligne 1) utilise `from src.kimi_proxy.config.loader import get_log_watcher_config, LogWatcherConfig` au lieu de `from kimi_proxy.config.loader import ...`.


* **Test de sécurité factice** : Dans `tests/unit/test_security_audit_remediations.py`, `test_eval_replacement()` appelle directement `ast.literal_eval(hostile_input)` sans tester aucune fonction de `kimi_proxy.proxy.tool_utils`.


* **Sensibilité à l'environnement (`KIMI_ADMIN_KEY`)** : `tests/e2e/test_regression.py` et `tests/unit/test_models_routes.py` ne réinitialisent pas `_ADMIN_KEY` et n'envoient pas d'en-tête `X-Admin-Key`, ce qui provoque des échecs `401` si `KIMI_ADMIN_KEY` est défini dans l'environnement d'exécution.


* **Cas limites non couverts** :
* Erreur amont `>= 400` en mode `stream=True` sur `/v1/chat/completions` (vérification de la fermeture de `response` et `_client_ref`).


* Envoi d'un corps non-JSON à `POST /api/mcp-gateway/{server_name}/rpc` (vérification du code JSON-RPC `-32700` et statut `400`).







---

### 6. Synthèse des Anomalies et Plan de Remédiation

| Identifiant Anomalie | Catégorie de Risque | Conséquence en Production | Sévérité |
| --- | --- | --- | --- |
| **ANOM-01** | Fuite de ressources (`proxy/passthrough.py`) | Fuite d'un `httpx.AsyncClient` et de sockets ouverts à chaque erreur HTTP `>= 400` en mode streaming (`_client_ref` non fermé). | Critique |
| **ANOM-02** | Robustesse API (`api/routes/mcp_gateway.py`) | Crash HTTP 500 non géré (`JSONDecodeError`) sur `POST /api/mcp-gateway/{server}/rpc` lorsque le payload n'est pas un JSON valide. | Critique |
| **ANOM-03** | Architecture 5 couches (`proxy/context_pruning.py` & `core/database.py`) | Dépendances inversées illégales `Proxy -> API` et `Core -> Config`, brisant l'isolation modulaire. | Haute |
| **ANOM-04** | Performance / Concurrence (`memory.py`, `storage.py`, `local_rag.py`) | Blocage de l'event loop `asyncio` par SQLite synchrone, `pbkdf2_hmac` et `SentenceTransformer.encode`. | Haute |
| **ANOM-05** | Fuites mémoire (`memory.py`, `client.py`, `server.py`, `watcher.py`, `tool_utils.py`) | Croissance infinie en RAM de `_local_cache`, `_tool_cache`, `PruneStore._items`, `_sessions` et `failure_reasons`. | Haute |
| **ANOM-06** | Sécurité (`api/dependencies.py` & `proxy/passthrough.py`) | Comparaison de clé admin vulnérable aux timing attacks (`!=`) et absence de filtrage des IP privées en mode dev sur HTTPS. | Haute |
| **ANOM-07** | Maintenabilité / SonarCloud S3776 (`mcp_pruner/server.py`, `engine.py`) | Complexité cognitive > 25 dans `_tool_prune_text` et `maybe_prune_jsonrpc_response`, fichier mort `client.py.backup` conservé. | Haute |
| **ANOM-08** | Conformité Standards & Tests (`dependencies.py`, `test_config_log_watcher.py`, `test_security_audit_remediations.py`) | Messages d'erreur en anglais dans `dependencies.py`, import `src.kimi_proxy` invalide et test `eval` factice. | Moyenne |

---

### Correctifs Prêts à Intégrer

#### 1. Correction de la fuite HTTPX en streaming et durcissement SSRF (`src/kimi_proxy/proxy/passthrough.py`)

Ferme systématiquement la réponse et le client `_client_ref` en cas de code HTTP `>= 400` sur un flux SSE, et bloque les adresses IP privées/link-local même hors production (sauf loopback explicite).

```python
# Dans src/kimi_proxy/proxy/passthrough.py — validate_and_normalize_target_url
    # Protection SSRF : blocage systématique des IPs privées/link-local/multicast
    # (autorise uniquement loopback en mode development)
    for ip_str in resolved_ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError as ip_err:
            raise ValueError(f"Adresse IP invalide résolue ({ip_str}) : {ip_err}") from ip_err

        if ip.is_loopback:
            if env == "production":
                raise ValueError(f"Accès à une adresse IP interdite/privée ({ip_str}) détecté.")
            continue

        if ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError(f"Accès à une adresse IP interdite/privée ({ip_str}) détecté.")

```

```python
# Dans src/kimi_proxy/proxy/passthrough.py — PassthroughProcessor.forward
        try:
            if is_streaming:
                response = await proxy_client.send_streaming(
                    req, provider_type=provider_type
                )

                if response.status_code >= 400:
                    try:
                        error_text = await response.aread()
                        text = error_text.decode("utf-8", errors="ignore")[:500]
                    finally:
                        await response.aclose()
                        client_ref = getattr(response, "_client_ref", None)
                        if client_ref is not None:
                            await client_ref.aclose()
                    print(f"❌ [PASSTHROUGH] Erreur {response.status_code}: {text}")
                    return JSONResponse(
                        content={"error": text, "code": response.status_code},
                        status_code=response.status_code,
                    )

```

#### 2. Sécurisation constante et francisation de l'authentification (`src/kimi_proxy/api/dependencies.py`)

Utilise `secrets.compare_digest` contre les attaques temporelles, lit l'environnement dynamiquement pour la testabilité, et francise tous les diagnostics conformément à `codingstandards.md`.

```python
"""Dépendances communes pour l'API Kimi Proxy."""
import os
import secrets
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.exceptions import ConfigurationError

security_bearer = HTTPBearer(auto_error=False)


def _get_admin_key() -> str:
    env = os.getenv("KIMI_ENV", "development").strip().lower()
    admin_key = os.getenv("KIMI_ADMIN_KEY", "").strip()
    if env == "production" and not admin_key:
        raise ConfigurationError(
            message="La variable d'environnement KIMI_ADMIN_KEY est obligatoire en mode production.",
            config_key="KIMI_ADMIN_KEY",
        )
    return admin_key


if os.getenv("KIMI_ENV", "development").strip().lower() == "production" and not os.getenv("KIMI_ADMIN_KEY", "").strip():
    raise ConfigurationError(
        message="La variable d'environnement KIMI_ADMIN_KEY est obligatoire en mode production.",
        config_key="KIMI_ADMIN_KEY",
    )


async def verify_admin_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> None:
    """Valide la clé admin via Authorization Bearer ou X-Admin-Key en temps constant."""
    admin_key = _get_admin_key()
    if not admin_key:
        return

    token = credentials.credentials if credentials else request.headers.get("x-admin-key")
    if not token or not secrets.compare_digest(token.strip(), admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autorisé : clé d'administration invalide ou manquante.",
        )


async def verify_admin_key_x_header(request: Request) -> None:
    """Valide la clé admin uniquement via X-Admin-Key en temps constant."""
    admin_key = _get_admin_key()
    if not admin_key:
        return

    token = request.headers.get("x-admin-key")
    if not token or not secrets.compare_digest(token.strip(), admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autorisé : clé d'administration invalide ou manquante.",
        )

```

#### 3. Gestion du Parse Error JSON-RPC dans la Gateway (`src/kimi_proxy/api/routes/mcp_gateway.py`)

Protège `await request.json()` contre les payloads JSON malformés et retourne une erreur JSON-RPC 2.0 standard `-32700` avec code HTTP `400`.

```python
@router.post("/mcp-gateway/{server_name}/rpc")
async def api_mcp_gateway_rpc(server_name: str, request: Request) -> JSONResponse:
    """Forwarde un JSON-RPC 2.0 brut vers un serveur MCP local puis masque la réponse."""
    service = MCPGatewayService()
    try:
        request_json_obj: object = await request.json()
    except json.JSONDecodeError:
        error_payload = service.build_jsonrpc_error(
            None, code=-32700, message="Erreur de parsing JSON-RPC (JSON invalide)"
        )
        return JSONResponse(content=error_payload, status_code=400)

    request_json = _as_dict(request_json_obj)
    if request_json is None:
        error_payload = service.build_jsonrpc_error(
            request_json_obj, code=-32600, message="Requête JSON-RPC invalide (attendu objet JSON)"
        )
        return JSONResponse(content=error_payload, status_code=400)

```

#### 4. Élimination des fuites mémoire et déport asynchrone SQLite / ML (`memory.py`, `server.py`, `local_rag.py`)

Supprime l'attribut inutilisé `_local_cache` de `MemoryManager`, exécute les requêtes SQLite et l'encodage `SentenceTransformer` via `asyncio.to_thread`, et borne `PruneStore` à `max_items=512`.

```python
# Dans src/kimi_proxy/features/mcp_pruner/local_rag.py — compute_local_rag_keep_set
import asyncio

async def compute_local_rag_keep_set(
    *,
    lines: list[str],
    current_keep_set: set[int],
    goal_hint: str,
    keep_target: int,
    model_name: str = "all-MiniLM-L6-v2",
) -> set[int]:
    """Calcule le nouveau keep_set via similarité cosinus hors de l'event loop asyncio."""
    if not current_keep_set or keep_target <= 0:
        return set()

    active_indices = sorted(list(current_keep_set))
    if len(active_indices) <= keep_target:
        return current_keep_set.copy()

    def _run_sync_rag() -> set[int]:
        active_lines = [lines[i] for i in active_indices]
        embedder = EmbeddingModel(model_name)
        line_embeddings = embedder.embed(active_lines)
        query_embedding = embedder.embed_single(goal_hint)
        store = VectorStore()
        store.add(line_embeddings, active_lines)
        results = store.query(query_embedding, top_k=keep_target)
        return {active_indices[r.index] for r in results}

    return await asyncio.to_thread(_run_sync_rag)

```

```python
# Dans src/kimi_proxy/features/mcp_pruner/server.py — PruneStore borné
class PruneStore:
    """Store mémoire borné (TTL + max_items) pour `recover_text`."""

    def __init__(self, *, ttl_s: int, max_items: int = 512) -> None:
        self._ttl_s = max(1, int(ttl_s))
        self._max_items = max(1, int(max_items))
        self._lock = asyncio.Lock()
        self._items: dict[str, _StoredPrune] = {}

    async def put(self, prune_id: str, *, lines: list[str]) -> None:
        now = time.time()
        async with self._lock:
            self._items[prune_id] = _StoredPrune(created_at_s=now, lines=lines)
            self._gc_locked(now)
            if len(self._items) > self._max_items:
                oldest = sorted(self._items.items(), key=lambda kv: kv[1].created_at_s)
                for k, _ in oldest[: len(self._items) - self._max_items]:
                    del self._items[k]

```