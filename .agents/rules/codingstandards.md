---
trigger: always_on
description: Kimi Proxy Middleware MCP coding standards - 5-layer architecture, async Python, SSE streaming
globs: "**/*.py"
---

# Kimi Proxy Middleware MCP Coding Standards

## 1. Architecture (5 Couches)
```
API (FastAPI) ← Services (SSE/Streaming) ← Features (MCP/Context) ← Proxy (HTTPX Passthrough) ← Core (SQLite MCP Memory)
```
- **Dépendance descendante stricte** : chaque couche ne dépend que des couches inférieures. Core est sans dépendance externe.
- **Pure headless middleware** : passthrough session-less piloté par les headers `X-Target-Base-URL` et `Authorization`.

## 2. Règles Python & Async
- **Async/Await obligatoire** : I/O asynchrone exclusive via `httpx.AsyncClient()`. `requests` est strictement interdit.
- **Résilience HTTPX** : capture et traitement obligatoires de `httpx.TimeoutException` et `httpx.ReadError` sur les flux.
- **Typage strict** : `Any` proscrit pour la logique domaine (réservé aux payloads JSON bruts). `TypedDict` pour les structures.
- **Comptage de tokens exact** : utilisation obligatoire de `tiktoken` (`cl100k_base`). Estimations empiriques (`len * 1.3`) interdites.
- **Complexité cognitive (SonarCloud S3776)** : score strictly <= 15 par fonction, max 3 niveaux d'indentation.
- **Patterns d'injection** : factory contextmanager pour SQLite MCP DB, DI FastAPI (`Header(...)`) pour `target_base_url`.

## 3. Streaming SSE & API
- **SSE natif** : `StreamingResponse` avec générateurs asynchrones non-bloquants (`data: {...}\n\n`). WebSockets (`/ws`) dépréciés.
- **Relay SSE optimisé** : passthrough via `async for chunk in response.aiter_bytes(): yield chunk` sans buffer intermédiaire.
- **Routes standards** : maintenir strictement `/models` et `/v1/chat/completions`. Pas de routes exotiques spécifiques aux éditeurs.
- **Mapping modèles** : résolution simple (clé exacte puis split par suffixe). Pas de fuzzy matching ou de normalisation lourde.

## 4. MCP Gateway & Mémoire
- **Tables actives** : `mcp_memory_entries` (mémoire standardisée) et `masked_content` (sanitizer read-only).
- **Asynchronisme DB** : écritures asynchrones, partitionnement par `session_id` et `memory_type`.
- **Cache Gateway** : TTL borné à 30 s (`_GATEWAY_CACHE_TTL = 30.0`), max 512 entrées, copie profonde avant retour.
- **Validation Workspace** : `Path(path).resolve().relative_to(allowed_root)` obligatoire contre le path traversal.

## 5. Sécurité, Langue & Anti-Patrons
- **Secrets** : uniquement dans `config.toml` via expansion `${VAR}` (`loader.py`). Zéro secret codé en dur.
- **Diagnostics en français** : logs système, messages d'erreurs HTTP et payloads de diagnostic obligatoirement en français.
- **Anti-patrons formellement interdits** :
  - ❌ État global / singletons (`sqlite3.connect` global).
  - ❌ Imports circulaires (utiliser `TYPE_CHECKING` si nécessaire).
  - ❌ `try...except` silencieux sans logging ni relance.
  - ❌ I/O bloquante sur la boucle d'événements.

## 6. Tests & Commandes
- **Tests async** : `pytest-asyncio` obligatoire, fixture DB SQLite mémoire (`:memory:`), mocks `httpx.AsyncClient`.
- **Exécution** :
  ```bash
  ./bin/kimi-proxy start --reload      # Démarrage dev
  ./bin/kimi-proxy test                # Suite de tests (pytest)
  ./scripts/start-mcp-servers.sh start # Serveurs MCP locaux
  ```
- **Documentation** : toute mise à jour documentaire doit respecter `.agents/skills/documentation/SKILL.md`.
