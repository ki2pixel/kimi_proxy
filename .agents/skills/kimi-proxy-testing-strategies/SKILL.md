---
name: kimi-proxy-testing-strategies
description: Comprehensive testing strategies for Kimi Proxy Middleware MCP. Use when writing or debugging tests with pytest, pytest-asyncio, httpx.ASGITransport, and monkeypatch.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Testing Strategies

**TL;DR**: la suite réelle utilise `pytest`, `pytest-asyncio` (`asyncio_mode = auto`), `httpx.ASGITransport` pour les routes ASGI, et `monkeypatch` / `unittest.mock.patch`. Les tests MCP fantômes ont été supprimés.

## Source of Truth

- `pytest.ini` (racine)
- `tests/conftest.py`
- `tests/unit/`
- `tests/integration/`
- `tests/e2e/`

## Layout actuel

| Dossier | Contenu |
| :--- | :--- |
| `tests/unit/` | Tests isolés (tokens, DB, proxy, features) |
| `tests/integration/` | Routes FastAPI, passthrough, features MCP |
| `tests/e2e/` | Régression API, streaming, smoke passthrough |
| `tests/fixtures/` | Fixtures partagées |
| `tests/mcp/harness_bridge_stdio_limits.py` | Harness manuel, non collecté par pytest |

`tests/mcp/`, `tests/run_mcp_tests.py`, `tests/run_mcp_tests_quick.sh` et `tests/pytest.ini` ont été supprimés.

## Async

`pytest.ini` active `asyncio_mode = auto`. Ne pas redéfinir `event_loop` dans `conftest.py`.

```python
import httpx
import pytest

@pytest.fixture
async def async_client():
    transport = httpx.ASGITransport(app=make_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

## Mocking

Patterns dominants :

- `monkeypatch.setenv(...)`
- `monkeypatch.setattr(module, "symbol", fake)`
- `unittest.mock.patch(...)`
- `AsyncMock` pour les callbacks async

### Passthrough

Pour tester `/v1/chat/completions`, patcher :

- `kimi_proxy.api.routes.mcp_passthrough.get_config`
- `kimi_proxy.proxy.passthrough.get_config`
- `kimi_proxy.proxy.passthrough.create_proxy_client`

Le fake client capture `request.content` et retourne `httpx.Response(200, ...)`.

```python
from tests.integration.passthrough_test_utils import (
    make_app, patch_passthrough, target_headers,
)
```

## Commandes

```bash
./bin/kimi-proxy test
PYTHONPATH=src venv/bin/python -m pytest tests/ -q
PYTHONPATH=src venv/bin/python -m pytest tests/unit -q
PYTHONPATH=src venv/bin/python -m pytest tests/integration -q
PYTHONPATH=src venv/bin/python -m pytest tests/e2e -q
```

La CLI `./bin/kimi-proxy test` propage désormais ses arguments à pytest :

```bash
./bin/kimi-proxy test -k "mcp_gateway or mcp_pruner" -q
./bin/kimi-proxy test tests/unit/proxy/test_stream.py -q
```

## Couverture utile

- Tokens : `tests/unit/test_tokens.py`
- DB : `tests/unit/test_database_optional_persistence.py`
- Streaming : `tests/unit/proxy/test_stream.py`, `tests/e2e/test_streaming_errors.py`
- Passthrough : `tests/e2e/test_regression.py`, tests d'intégration sous `tests/integration/`
- Gateway MCP : `tests/unit/features/test_mcp_gateway.py`
- Bridge : `tests/unit/test_mcp_bridge.py`
- Pruner : `tests/unit/features/test_mcp_pruner_*.py`

## ❌ À éviter

- Réintroduire `tests/mcp/` ou `tests/pytest.ini`.
- Réintroduire un fixture `event_loop`.
- Tester `/chat/completions`, `/api/sessions/*`, `/api/compaction/*`, `/api/compress/*`.
- Mocker globalement `httpx.AsyncClient` si le test utilise aussi un client ASGI.
- Ajouter des `pytest.skip` silencieux pour masquer une régression.

## Golden Rule

**Testez le chemin réel : `/v1/chat/completions` → features → fake HTTPX → SSE ou JSON.** Un test qui ne passe que sur une route supprimée est un test mort.
