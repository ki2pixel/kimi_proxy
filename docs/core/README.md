# Core Layer — Fondations

**TL;DR** : la couche Core ne dépend d'aucun package externe. Elle fournit SQLite, le comptage Tiktoken, les dataclasses MCP et les constantes partagées.

## Problème

Le middleware doit compter des tokens avec précision, persister un petit état MCP et exposer des structures typées sans tirer de framework dans les couches basses. Toute dépendance externe dans Core rendrait les tests et le remplacement de l'infrastructure plus coûteux.

## Rôle dans l'architecture

```text
API (FastAPI) ← Services (streaming) ← Features (MCP/contexte) ← Proxy (HTTPX) ← Core (SQLite, Tiktoken, modèles)
```

Core ne connaît ni FastAPI, ni HTTPX, ni les serveurs MCP. Il ne fait aucun appel réseau.

## Composants

### `database.py`

- Connexion SQLite synchrone via `sqlite3`, encapsulée par `get_db()`.
- Mode par défaut : base en mémoire partagée (`:memory:`).
- Mode persistant : activé par `KIMI_PERSIST_SESSIONS=true` ou `[database].persist_sessions=true`.
- Schéma réduit à deux tables :
  - `masked_content` : lecture des contenus masqués par les routes sanitizer.
  - `mcp_memory_entries` : mémoire MCP fréquente, épisodique et sémantique.
- Aucune migration `ALTER TABLE` n'est exécutée au démarrage. Les anciennes tables éventuellement présentes dans un fichier SQLite existant ne sont pas supprimées automatiquement.

### `tokens.py`

- `count_tokens_tiktoken(messages)` compte une liste de messages OpenAI avec l'encodage `cl100k_base`.
- `count_tokens_text(text)` compte un texte simple.
- Le comptage est synchrone et CPU-bound ; il doit rester sur des payloads bornés.

### `models.py`

Dataclasses réellement utilisées :

- `MCPMemoryEntry`, `MCPToolCall`, `QdrantSearchResult`, `MCPCluster`, `MCPCompressionResult`, `MCPExternalServerStatus` pour la couche MCP.
- `TokenMetrics`, `AnalyticsEvent`, `AnalyticsSourceState` pour le log watcher.

Les modèles de sessions, métriques historiques, compaction et Phase 4 ont été supprimés avec leurs pipelines.

### `constants.py` et `exceptions.py`

- Constantes partagées : contexte maximal, fichier SQLite, configuration sanitizer, circuit breaker MCP, chemins du log watcher.
- Exceptions conservées : `KimiProxyError`, `ConfigurationError`, `TokenizationError`, `CompactionError`.

## Invariants

1. Aucun import FastAPI/HTTPX/serveur MCP dans Core.
2. Aucune I/O réseau.
3. Les erreurs de configuration remontent en `ConfigurationError` avec un message français.
4. Les tables SQL sont créées de manière idempotente (`CREATE TABLE IF NOT EXISTS`).
5. Un fichier SQLite existant n'est jamais migré ou purgé silencieusement.

## Trade-offs

| Choix | Avantage | Limite |
| :--- | :--- | :--- |
| SQLite synchrone | Zéro dépendance, tests simples | Appels bloquants si utilisés dans un handler async |
| Base en mémoire par défaut | Démarrage rapide, pas d'artefact disque | Données perdues au redémarrage |
| Schéma minimal | Maintenance et audit simples | Pas de rétention historique des métriques |

## Golden Rule

**Core reste petit, synchrone et sans dépendance externe.** Toute logique réseau, MCP ou FastAPI appartient aux couches supérieures.
