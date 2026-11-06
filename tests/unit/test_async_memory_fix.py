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
