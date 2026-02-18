"""
Tests d'intégration de la facade MCP.

Vérifie la compatibilité ascendante, le singleton, et la délégation aux clients spécialisés.
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from kimi_proxy.features.mcp.client import (
    MCPExternalClient,
    get_mcp_client,
    reset_mcp_client,
)
from kimi_proxy.features.mcp.base.config import MCPClientConfig
from kimi_proxy.features.mcp.base.rpc import MCPRPCClient
from kimi_proxy.features.mcp.servers import (
    QdrantMCPClient,
    CompressionMCPClient,
    TaskMasterMCPClient,
    SequentialThinkingMCPClient,
    FileSystemMCPClient,
    JsonQueryMCPClient,
)


# Fixtures
def mock_config():
    """Configuration de test."""
    return MCPClientConfig(
        qdrant_url="http://localhost:6333",
        compression_url="http://localhost:8001",
        task_master_url="http://localhost:8002",
        sequential_thinking_url="http://localhost:8003",
        fast_filesystem_url="http://localhost:8004",
        json_query_url="http://localhost:8005",
        max_retries=2,
        retry_delay_ms=50.0,
    )


@pytest.fixture
def config():
    """Fixture config."""
    return mock_config()


@pytest.fixture
def client(config):
    """Fixture client MCP."""
    return MCPExternalClient(config)


# Tests de chargement
def test_client_initialization(config):
    """Vérifie que le client se charge avec config."""
    client = MCPExternalClient(config)
    
    # Vérifie que tous les clients spécialisés sont présents
    assert isinstance(client.qdrant, QdrantMCPClient)
    assert isinstance(client.compression, CompressionMCPClient)
    assert isinstance(client.task_master, TaskMasterMCPClient)
    assert isinstance(client.sequential, SequentialThinkingMCPClient)
    assert isinstance(client.filesystem, FileSystemMCPClient)
    assert isinstance(client.json_query, JsonQueryMCPClient)
    
    # Vérifie l'instance de RPC
    assert isinstance(client._rpc_client, MCPRPCClient)
    assert client._rpc_client.max_retries == 2


def test_client_default_config():
    """Vérifie que le client se charge avec config par défaut."""
    client = MCPExternalClient()
    
    # Vérifie la config par défaut
    assert client.config.qdrant_url == "http://localhost:6333"
    assert client.config.compression_url == "http://localhost:8001"
    assert client.config.max_retries == 3


# Tests de singleton
def test_get_mcp_client_singleton():
    """Vérifie le pattern singleton."""
    # Réinitialise le singleton
    reset_mcp_client()
    
    # Crée deux instances
    client1 = get_mcp_client()
    client2 = get_mcp_client()
    
    # Même instance
    assert client1 is client2
    assert isinstance(client1, MCPExternalClient)


def test_reset_mcp_client():
    """Vérifie la réinitialisation du singleton."""
    reset_mcp_client()
    client1 = get_mcp_client()
    
    # Réinitialise et recrée
    reset_mcp_client()
    client2 = get_mcp_client()
    
    # Nouvelle instance
    assert client1 is not client2


def test_get_mcp_client_with_config():
    """Vérifie la création avec config custom."""
    reset_mcp_client()
    config = MCPClientConfig(max_retries=5)
    
    client = get_mcp_client(config)
    
    assert client.config.max_retries == 5


# Tests de délégation (mockés)
@pytest.mark.asyncio
async def test_qdrant_delegation(config):
    """Vérifie que la facade délègue à qdrant."""
    client = MCPExternalClient(config)
    
    # Mock le client qdrant
    with patch.object(client.qdrant, 'check_status', new_callable=AsyncMock) as mock_status:
        mock_status.return_value = Mock(connected=True)
        
        result = await client.check_qdrant_status()
        
        # Vérifie que qdrant.check_status a été appelé
        mock_status.assert_called_once()
        assert result.connected is True


@pytest.mark.asyncio
async def test_compression_delegation(config):
    """Vérifie que la facade délègue à compression."""
    client = MCPExternalClient(config)
    
    with patch.object(client.compression, 'compress', new_callable=AsyncMock) as mock_compress:
        from kimi_proxy.core.tokens import count_tokens_text
        original_tokens = count_tokens_text("Hello " * 20)
        mock_result = Mock(
            original_tokens=original_tokens,
            compressed_tokens=int(original_tokens * 0.7),
            compression_ratio=0.3
        )
        mock_compress.return_value = mock_result
        
        result = await client.compress_content("Hello " * 20, algorithm="zlib")
        
        # Vérifie la délégation
        mock_compress.assert_called_once()
        assert result.compression_ratio == 0.3


@pytest.mark.asyncio
async def test_task_master_delegation(config):
    """Vérifie que la facade délègue à task_master."""
    client = MCPExternalClient(config)
    
    with patch.object(client.task_master, 'call_tool', new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {"tasks": [{"id": 1, "title": "Test"}]}
        
        result = await client.call_task_master_tool("get_tasks", {})
        
        mock_call.assert_called_once_with("get_tasks", {})
        assert "tasks" in result


@pytest.mark.asyncio
async def test_sequential_delegation(config):
    """Vérifie que la facade délègue à sequential."""
    client = MCPExternalClient(config)
    
    with patch.object(client.sequential, 'call_tool', new_callable=AsyncMock) as mock_call:
        from kimi_proxy.core.models import SequentialThinkingStep
        mock_step = Mock(
            step_number=1,
            thought="Test thought",
            next_thought_needed=True,
            total_thoughts=5,
            branches=[]
        )
        mock_call.return_value = mock_step
        
        result = await client.call_sequential_thinking("Test thought", 1, 5)
        
        mock_call.assert_called_once()
        assert result.step_number == 1


@pytest.mark.asyncio
async def test_filesystem_delegation(config):
    """Vérifie que la facade délègue à filesystem."""
    client = MCPExternalClient(config)
    
    with patch.object(client.filesystem, 'call_tool', new_callable=AsyncMock) as mock_call:
        from kimi_proxy.core.models import FileSystemResult
        mock_result = Mock(
            success=True,
            path="/tmp/test",
            operation="fast_read_file",
            content="Hello World",
            bytes_affected=11
        )
        mock_call.return_value = mock_result
        
        result = await client.call_fast_filesystem_tool("fast_read_file", {"path": "/tmp/test"})
        
        mock_call.assert_called_once_with("fast_read_file", {"path": "/tmp/test"})
        assert result.success is True


@pytest.mark.asyncio
async def test_json_query_delegation(config):
    """Vérifie que la facade délègue à json_query."""
    client = MCPExternalClient(config)
    
    with patch.object(client.json_query, 'call_tool', new_callable=AsyncMock) as mock_call:
        from kimi_proxy.core.models import JsonQueryResult
        mock_result = Mock(
            success=True,
            query="$.store.book",
            file_path="books.json",
            results=[{"title": "Book1"}],
            execution_time_ms=5
        )
        mock_call.return_value = mock_result
        
        result = await client.call_json_query_tool("json_query_jsonpath", "books.json", "$.store.book")
        
        mock_call.assert_called_once()
        assert result.success is True


# Tests de cache de statut
def test_status_cache_isolation(config):
    """Vérifie que les statuts sont isolés par serveur."""
    client = MCPExternalClient(config)
    
    # Vérifie que le cache est vide initialement
    assert len(client._status_cache) == 0
    
    # Mock les clients pour éviter les appels async
    with patch.object(client.qdrant, '_status', Mock(connected=True)) as mock_qdrant:
        client._status_cache["qdrant"] = mock_qdrant
        
    with patch.object(client.compression, '_status', Mock(connected=True)) as mock_compression:
        client._status_cache["compression"] = mock_compression
    
    # Les statuts sont bien isolés
    assert "qdrant" in client._status_cache
    assert "compression" in client._status_cache


# Tests de helpers
def test_helper_methods_exist(config):
    """Vérifie que les méthodes helpers sont présentes."""
    client = MCPExternalClient(config)
    
    # Vérifie que les helpers sont disponibles
    assert hasattr(client, 'fast_read_file')
    assert hasattr(client, 'fast_write_file')
    assert hasattr(client, 'fast_search_code')
    assert hasattr(client, 'fast_list_directory')
    assert hasattr(client, 'jsonpath_query')
    assert hasattr(client, 'search_json_keys')
    assert hasattr(client, 'search_json_values')


@pytest.mark.asyncio
async def test_all_server_statuses_isolation(config):
    """Vérifie que les statuts sont bien isolés par serveur."""
    client = MCPExternalClient(config)
    
    # Mock chaque client.specialized.check_status
    with patch.object(client.qdrant, 'check_status', new_callable=AsyncMock) as mock_qdrant, \
         patch.object(client.compression, 'check_status', new_callable=AsyncMock) as mock_compression, \
         patch.object(client.task_master, 'check_status', new_callable=AsyncMock) as mock_task_master, \
         patch.object(client.sequential, 'check_status', new_callable=AsyncMock) as mock_sequential, \
         patch.object(client.filesystem, 'check_status', new_callable=AsyncMock) as mock_filesystem, \
         patch.object(client.json_query, 'check_status', new_callable=AsyncMock) as mock_json_query:
        
        # Définir des retours différents
        mock_qdrant.return_value = Mock(connected=True)
        mock_compression.return_value = Mock(connected=True)
        mock_task_master.return_value = Mock(connected=False)
        mock_sequential.return_value = Mock(connected=True)
        mock_filesystem.return_value = Mock(connected=False)
        mock_json_query.return_value = Mock(connected=True)
        
        # Appelle la méthode globale
        statuses = await client.get_all_phase4_server_statuses()
        
        # Vérifie que tous les check_status ont été appelés
        mock_qdrant.assert_called_once()
        mock_compression.assert_called_once()
        mock_task_master.assert_called_once()
        mock_sequential.assert_called_once()
        mock_filesystem.assert_called_once()
        mock_json_query.assert_called_once()
        
        # Vérifie le nombre de statuts
        assert len(statuses) == 4  # Phase 4


@pytest.mark.asyncio
async def test_close_method(config):
    """Vérifie que close() ferme proprement les connexions."""
    client = MCPExternalClient(config)
    
    # Mock la méthode close du rpc client
    with patch.object(client._rpc_client, 'aclose', new_callable=AsyncMock) as mock_close:
        await client.close()
        
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_call_mcp_tool_generic_failure():
    """Vérifie que call_mcp_tool gère les erreurs."""
    client = MCPExternalClient()
    
    result = await client.call_mcp_tool("unknown_server", "unknown_tool", {})
    
    assert result.status == "error"
    assert "inconnu" in result.result["error"]


if __name__ == "__main__":
    pytest.main([__file__])