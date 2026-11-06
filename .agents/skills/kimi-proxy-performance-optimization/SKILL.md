---
name: kimi-proxy-performance-optimization
description: Performance optimization expert for Kimi Proxy Middleware MCP. Use when optimizing token counting, SQLite queries, SSE streaming, MCP gateway caching, or MCP pruning.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Performance Optimization

**TL;DR**: Les optimisations réellement présentes sont le relay SSE sans buffer, le cache TTL du gateway MCP, les index SQLite sur `mcp_memory_entries`, le comptage Tiktoken et le pruning MCP. Ne documentez pas de helpers supprimés.

## Source of Truth

- `src/kimi_proxy/proxy/stream.py` : relay SSE pur.
- `src/kimi_proxy/proxy/client.py` : HTTPX, timeouts, retry réseau.
- `src/kimi_proxy/core/database.py` : SQLite minimal.
- `src/kimi_proxy/core/tokens.py` : comptage Tiktoken.
- `src/kimi_proxy/api/routes/mcp_gateway.py` : cache TTL et circuit breaker.
- `src/kimi_proxy/features/mcp_pruner/` : pruning heuristique, local RAG et DeepInfra.
- `src/kimi_proxy/features/mcp_tool_pruning/` : pruning des réponses tools/call.

## Optimisations actuelles

### 1. Streaming SSE sans buffer

`stream_generator` relaie les octets dès réception et ferme la réponse et le client HTTPX dans `finally`. Il n'accumule plus 256 Ko pour extraire des tokens.

```python
async for chunk in response.aiter_bytes():
    yield chunk
```

Conséquence : mémoire bornée par le chunk courant, pas par la durée du stream.

### 2. Comptage Tiktoken

- `count_tokens_tiktoken(messages)` pour une liste de messages.
- `count_tokens_text(text)` pour un texte.
- Le comptage reste CPU-bound ; évitez de l'appeler sur des payloads non bornés dans une boucle async.

### 3. SQLite

Deux tables et trois index :

- `masked_content` (lecture sanitizer).
- `mcp_memory_entries`.
- `idx_memory_type`, `idx_memory_session`, `idx_memory_access`.

La base est en mémoire par défaut. En mode fichier, les requêtes utilisent des paramètres SQL et `sqlite3.Row`.

### 4. Cache et circuit breaker du gateway MCP

`api/routes/mcp_gateway.py` :

- cache TTL de 30 s pour les opérations de lecture ;
- cache borné à 512 entrées avec éviction FIFO ;
- copie profonde avant retour pour éviter la mutation du cache ;
- circuit breaker par serveur avec fenêtre TTL de 30 s.

### 5. Pruning MCP

- `mcp_pruner` : pipeline `heuristic`, `local_rag`, `deepinfra`, cache TTL configurable.
- `mcp_tool_pruning` : élague les réponses `tools/call` volumineuses, avec fallback tête/queue et métriques.
- Les flags sont désactivés par défaut ; activez-les après mesure.

### 6. HTTPX

- Le client de streaming crée un `AsyncClient` par requête et le ferme à la fin du flux.
- Le client RPC MCP (`MCPRPCClient`) réutilise un `AsyncClient` avec limites de connexions.
- Les retries ne s'appliquent qu'aux erreurs réseau, pas aux 4xx/5xx.

## Mesure

```bash
PYTHONPATH=src venv/bin/python -m pytest tests/unit/features/test_mcp_pruner_server.py -q
PYTHONPATH=src venv/bin/python -m pytest tests/unit/features/test_mcp_tool_pruning_engine.py -q
PYTHONPATH=src venv/bin/python -m pytest tests/e2e/test_passthrough_smoke.py -q  # si présent
```

Pour SQLite en mode fichier :

```bash
sqlite3 sessions.db 'EXPLAIN QUERY PLAN SELECT * FROM mcp_memory_entries ORDER BY access_count DESC LIMIT 50;'
```

## ❌ Ne pas documenter comme actif

- `chunk_large_response` / `should_chunk_response` : supprimés.
- `vacuum_database` : supprimé.
- `_proxy_to_provider` : supprimé.
- Extraction de tokens post-stream et broadcast WebSocket : supprimés.
- `tests/mcp/test_mcp_compression.py` : la suite MCP fantôme a été supprimée.

## Golden Rule

**Mesurez le chemin réel `/v1/chat/completions` → features → HTTPX → SSE.** Toute optimisation qui ajoute un buffer, un broadcast ou un état global doit être justifiée par une mesure, pas par une intuition.
