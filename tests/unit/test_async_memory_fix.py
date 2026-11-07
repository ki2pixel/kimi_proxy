"""Tests de la gestion mémoire MCP."""
import inspect
from unittest.mock import MagicMock

import pytest

from kimi_proxy.core.database import init_database
from kimi_proxy.features.mcp.memory import MemoryManager


@pytest.mark.asyncio
async def test_memory_manager_store_memory_is_async():
    assert inspect.iscoroutinefunction(MemoryManager.store_memory)


@pytest.mark.asyncio
async def test_memory_manager_store_and_retrieve():
    init_database()
    manager = MemoryManager(mcp_client=MagicMock())

    entry = await manager.store_memory(
        session_id=42,
        content="Mémoire de test unique pour le middleware Kimi Proxy.",
        memory_type="episodic",
    )

    assert entry is not None
    assert entry.session_id == 42
    assert entry.memory_type == "episodic"
    assert entry.content_hash

    entries = await manager.get_frequent_memories(
        session_id=42,
        min_access_count=0,
        limit=5,
    )
    assert any(item.id == entry.id for item in entries)


@pytest.mark.asyncio
async def test_memory_manager_has_no_unbounded_local_cache():
    manager = MemoryManager(mcp_client=MagicMock())
    assert not hasattr(manager, "_local_cache")


@pytest.mark.asyncio
async def test_memory_manager_uses_db_thread_helper(monkeypatch):
    import kimi_proxy.features.mcp.memory as memory_mod

    init_database()
    calls: list[str] = []
    original = memory_mod.run_db_in_thread

    async def _fake_run_db_in_thread(fn, *args, **kwargs):
        calls.append(getattr(fn, "__name__", "inconnu"))
        return await original(fn, *args, **kwargs)

    monkeypatch.setattr(memory_mod, "run_db_in_thread", _fake_run_db_in_thread)
    manager = MemoryManager(mcp_client=MagicMock())

    await manager.store_memory(
        session_id=43,
        content="Mémoire de test pour vérifier le déport SQLite.",
        memory_type="episodic",
    )

    assert calls


def test_mcp_external_client_has_no_unbounded_tool_cache():
    from kimi_proxy.features.mcp.client import MCPExternalClient

    client = MCPExternalClient()
    assert not hasattr(client, "_tool_cache")


def test_sanitizer_storage_functions_are_async():
    from kimi_proxy.features.sanitizer import storage

    assert inspect.iscoroutinefunction(storage.get_masked_content)
    assert inspect.iscoroutinefunction(storage.list_masked_contents)
    assert inspect.iscoroutinefunction(storage.get_sanitizer_stats)


@pytest.mark.asyncio
async def test_sanitizer_stats_runs_off_event_loop():
    from kimi_proxy.features.sanitizer.storage import get_sanitizer_stats

    init_database()
    stats = await get_sanitizer_stats()

    assert isinstance(stats, dict)
    assert "total_masked" in stats
