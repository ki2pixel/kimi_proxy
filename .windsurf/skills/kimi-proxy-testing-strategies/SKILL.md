---
name: kimi-proxy-testing-strategies
description: Comprehensive testing strategies for Kimi Proxy Dashboard. Use when writing tests, debugging issues, or ensuring system reliability. Covers unit tests, integration tests, E2E testing, and performance testing with pytest-asyncio.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Testing Strategies

**TL;DR**: The real test stack uses `pytest`, `pytest-asyncio`, per-suite fixtures, `httpx.ASGITransport` for async API tests, and a mix of `monkeypatch`, `unittest.mock.patch`, and `AsyncMock`. Align new tests with the existing suite layout instead of relying on generic pytest examples that do not match the project.

## Source of Truth

Current testing behavior is spread across:

- `tests/conftest.py`
- `tests/pytest.ini`
- `tests/mcp/*`
- `tests/integration/*`
- `tests/e2e/*`
- selected `tests/unit/*`

## Current Test Layout

The project no longer fits a tiny three-folder mental model.

### Real high-level groups in use

- `tests/mcp/`: MCP-focused unit, integration, and real-server tests
- `tests/integration/`: FastAPI/route integration tests
- `tests/e2e/`: focused end-to-end and regression scenarios
- `tests/unit/`: lower-level targeted tests

## Async Testing Pattern

### Base fixtures already present

`tests/conftest.py` currently provides lightweight shared fixtures such as:

- `event_loop`
- `test_config`
- `sample_messages`

### Real async client pattern used in integration tests

```python
import httpx
import pytest

@pytest.fixture
async def async_client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

This pattern is more representative of the current codebase than a generic `AsyncClient(base_url="http://testserver")` example.

## Mocking and Patching

### ✅ Most common current tools

- `monkeypatch.setattr(...)`
- `unittest.mock.patch(...)`
- `AsyncMock`
- `MockTransport` for HTTPX

### Example aligned with the current style

```python
from unittest.mock import AsyncMock, patch

with patch('httpx.AsyncClient.send', side_effect=mock_send):
    ...
```

Use `mocker.patch(...)` only if the specific test suite already depends on the pytest-mock plugin. It is not the dominant pattern in the current repository.

## Pytest Configuration Reality Check

`tests/pytest.ini` is currently scoped to the MCP suite and contains markers such as:

- `asyncio`
- `unit`
- `integration`
- `e2e`
- `serial`
- `qdrant`
- `compression`
- `task_master`
- `filesystem`
- `json_query`

Do not describe it as the single universal config for every test category unless that structure is actually unified later.

## Performance and Load Testing

Performance coverage is real, but distributed.

Current examples include:

- `tests/mcp/test_mcp_compression.py`: small/large compression performance checks
- `tests/mcp/test_mcp_e2e_real_servers.py`: MCP latency benchmarking
- `tests/e2e/test_streaming_errors.py`: streaming robustness paths

When writing new performance tests, colocate them near the feature they measure.

## API and Gateway Test Guidance

For FastAPI routes and MCP gateway tests, prefer module-local async fixtures plus transport-level patching.

### Important pattern already used in the codebase

Patch the target module's `httpx.AsyncClient` symbol instead of globally patching HTTPX if the test also uses an ASGI client. This avoids breaking the test harness itself.

## Suggested Commands

### MCP-focused suite

```bash
PYTHONPATH=src python -m pytest tests/mcp -q
```

### Integration example

```bash
PYTHONPATH=src python -m pytest tests/integration -q
```

### Focused streaming regression

```bash
PYTHONPATH=src python -m pytest tests/e2e/test_streaming_errors.py -q
```

## ❌ Outdated Patterns to Avoid

- Assuming one global `async_client` fixture covers all suites
- Documenting `mocker.patch(...)` as the main project convention
- Treating `tests/pytest.ini` as a root-wide universal config when it is MCP-scoped today
- Describing CI workflows that are not present or not maintained in the repo

## Golden Rule

**Write tests the way this repository already tests itself: async first, HTTPX-based, transport-aware, and narrowly patched.** Update this skill when the real fixture or suite structure changes.