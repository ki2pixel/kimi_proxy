# Guide de codage pour agents IA — Kimi Proxy Middleware MCP

**TL;DR** : lisez `.agents/rules/codingstandards.md` pour les règles, puis ce guide pour les patterns actuels. Le runtime est session-less, SSE uniquement, et `config.toml` ne contient ni provider ni modèle.

## Architecture 5 couches

```text
API (FastAPI) ← Services (SSE/callbacks) ← Features (MCP/contexte) ← Proxy (HTTPX) ← Core (SQLite/Tiktoken)
```

Règles :

- Core n'importe aucun package externe.
- Les couches supérieures ne sont jamais importées par les couches inférieures.
- Pas de singleton d'état global non borné.
- Pas d'I/O synchrone dans un handler async.

## Patterns actuels

### Core

```python
from kimi_proxy.core.database import get_db
from kimi_proxy.core.tokens import count_tokens_text

with get_db() as conn:
    rows = conn.execute(
        "SELECT id FROM mcp_memory_entries WHERE session_id = ?",
        (session_id,),
    ).fetchall()
```

- SQLite minimal : `masked_content`, `mcp_memory_entries`.
- Pas de migration `ALTER TABLE` automatique.
- Comptage Tiktoken obligatoire, pas d'estimation.

### Features

```python
from kimi_proxy.features.mcp.memory import get_memory_manager

manager = get_memory_manager()
entry = await manager.store_memory(
    session_id=1,
    content="...",
    memory_type="episodic",
)
```

- Les features MCP sont désactivées par défaut quand elles modifient le contexte.
- Chaque flag doit avoir un fallback no-op et des logs français.
- Les clients MCP externes passent par `features/mcp/client.py`.

### Proxy

```python
from kimi_proxy.proxy.passthrough import PassthroughProcessor

processor = PassthroughProcessor(config)
body = await processor.apply_features(body_json)
return await processor.forward(body, raw_headers, request)
```

- `X-Target-Base-URL` est obligatoire.
- `Authorization` porte la clé provider.
- La validation SSRF est asynchrone.
- Le streaming est un relay SSE pur.

### API

```python
@router.post("/v1/chat/completions")
async def mcp_passthrough(request: Request):
    ...
```

- Ne pas ajouter de route de compatibilité sans consommateur identifié.
- Ne pas réintroduire `/chat/completions`, `/api/sessions/*`, `/api/compaction/*`, `/api/compress/*` ni `/ws`.
- `/api/*` est protégé par `KIMI_ADMIN_KEY`.
- `/v1/chat/completions` utilise `X-Admin-Key`, jamais `Authorization`, pour l'admin.

## Configuration

- `config.toml` ne contient ni `[providers]` ni `[models]`.
- Les secrets restent en `${VAR}`.
- Toute clé TOML doit être lue par un getter de `config/loader.py`.
- Ne pas ajouter de clé "au cas où".

## Tests

```bash
./bin/kimi-proxy test
PYTHONPATH=src venv/bin/python -m pytest tests/ -q
PYTHONPATH=src venv/bin/python -m pytest tests/unit/proxy/test_stream.py -q
PYTHONPATH=src venv/bin/python -m ruff check src tests --select F821,F811,F401
```

- Tests unitaires isolés dans `tests/unit/`.
- Tests d'intégration dans `tests/integration/`.
- Tests de fumée API dans `tests/e2e/`.
- Aucune exclusion silencieuse de tests dans la CLI.

## Documentation

- Appliquer `.agents/skills/documentation/SKILL.md`.
- Mettre à jour `docs/api/README.md` à chaque changement de route.
- Ne pas documenter une feature supprimée comme active.
- Marquer les documents historiques avec un avertissement.

## Ce qu'il ne faut pas réintroduire

- WebSocket, `ConnectionManager`, `broadcast`.
- Sessions, métriques, compaction, compression applicative.
- Rate limiter global inutilisé.
- Providers/modèles dans `config.toml`.
- `chunk_large_response`, `vacuum_database`, `_proxy_to_provider`.

## Golden Rule

**Le code mort se supprime, il ne se commente pas.** Si une feature est désactivée mais câblée et testée, elle est dormante ; si son point d'entrée a disparu, elle est morte.
