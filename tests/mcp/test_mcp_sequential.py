"""
Tests pour SequentialThinkingMCPClient.

Vérifie:
- Raisonnement séquentiel multi-étapes
- Branches alternatives
- Next thought needed flag
- Timeout et erreurs
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from kimi_proxy.features.mcp.servers.sequential import SequentialThinkingMCPClient
from kimi_proxy.features.mcp.base.config import MCPClientConfig


@pytest.fixture
def config():
    """Config de test."""
    return MCPClientConfig(
        sequential_thinking_url="http://localhost:8003",
        sequential_thinking_api_key="test_key",
        sequential_thinking_timeout_ms=60000.0,
    )


@pytest.fixture
def mock_rpc():
    """RPC mock."""
    rpc = Mock()
    rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Initial thought",
        "next_thought_needed": True,
        "total_thoughts": 5,
        "branches": []
    })
    return rpc


@pytest.fixture
def client(config, mock_rpc):
    """Client Sequential."""
    return SequentialThinkingMCPClient(config, mock_rpc)


@pytest.mark.asyncio
async def test_check_status_healthy(client, mock_rpc):
    """Test statut healthy."""
    status = await client.check_status()
    
    assert status.connected is True
    assert status.name == "sequential-thinking-mcp"
    assert "sequential_thinking" in status.capabilities
    assert "problem_solving" in status.capabilities
    assert status.tools_count == 1


@pytest.mark.asyncio
async def test_check_status_error(client, mock_rpc):
    """Test statut unhealthy."""
    mock_rpc.make_rpc_call = AsyncMock(side_effect=Exception("Connect error"))
    
    status = await client.check_status()
    
    assert status.connected is False
    assert status.error_count == 1


@pytest.mark.asyncio
async def test_call_tool_basic(client, mock_rpc):
    """Test appel de base."""
    result = await client.call_tool("Test problem")
    
    assert result.step_number == 1
    assert result.thought == "Initial thought"
    assert result.next_thought_needed is True
    assert result.total_thoughts == 5


@pytest.mark.asyncio
async def test_call_tool_custom_params(client, mock_rpc):
    """Test appel avec paramètres custom."""
    result = await client.call_tool(
        thought="Custom thought",
        thought_number=3,
        total_thoughts=10
    )
    
    # Vérifie les paramètres de l'appel RPC
    mock_rpc.make_rpc_call.assert_called_once()
    args = mock_rpc.make_rpc_call.call_args[1]["params"]
    assert args["thought"] == "Custom thought"
    assert args["thought_number"] == 3
    assert args["total_thoughts"] == 10


@pytest.mark.asyncio
async def test_call_tool_with_mcp_tools(client, mock_rpc):
    """Test avec liste des outils MCP disponibles."""
    available_tools = ["fast_read_file", "fast_write_file", "task_master"]
    
    await client.call_tool(
        "Problem",
        available_mcp_tools=available_tools
    )
    
    args = mock_rpc.make_rpc_call.call_args[1]["params"]
    assert args["available_mcp_tools"] == available_tools


@pytest.mark.asyncio
async def test_multi_step_reasoning(client, mock_rpc):
    """Test workflow multi-étapes."""
    # Étape 1
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Analyser le bug",
        "next_thought_needed": True,
        "total_thoughts": 3,
        "branches": []
    })
    
    step1 = await client.call_tool("Bug analysis", thought_number=1, total_thoughts=3)
    assert step1.next_thought_needed is True
    
    # Étape 2
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 2,
        "thought": "Vérifier les logs",
        "next_thought_needed": True,
        "total_thoughts": 3,
        "branches": []
    })
    
    step2 = await client.call_tool("Check logs", thought_number=2, total_thoughts=3)
    assert step2.step_number == 2
    
    # Étape 3 (dernière)
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 3,
        "thought": "Solution: fix line 42",
        "next_thought_needed": False,
        "total_thoughts": 3,
        "branches": []
    })
    
    step3 = await client.call_tool("Fix solution", thought_number=3, total_thoughts=3)
    assert step3.next_thought_needed is False


@pytest.mark.asyncio
async def test_branches_exploration(client, mock_rpc):
    """Test exploration avec branches alternatives."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Multiple approaches",
        "next_thought_needed": True,
        "total_thoughts": 5,
        "branches": [
            {"id": "A", "confidence": 0.8},
            {"id": "B", "confidence": 0.6}
        ]
    })
    
    result = await client.call_tool("Decision problem")
    
    assert len(result.branches) == 2
    assert result.branches[0]["id"] == "A"
    assert result.branches[0]["confidence"] == 0.8


@pytest.mark.asyncio
async def test_server_error_fallback(client, mock_rpc):
    """Test fallback quand serveur down."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    result = await client.call_tool("Problem without response")
    
    # Fallback avec données minimales
    assert result.step_number == 1  # Default
    assert result.thought == "Erreur: Aucune réponse du serveur"
    assert result.next_thought_needed is False


@pytest.mark.asyncio
async def test_timeout_respected(client, mock_rpc):
    """Test timeout à 60s respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Thought",
        "next_thought_needed": False,
        "total_thoughts": 1,
        "branches": []
    })
    
    await client.call_tool("Complex reasoning")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["timeout_ms"] == 60000.0


@pytest.mark.asyncio
async def test_thought_number_tracking(client, mock_rpc):
    """Test suivis correct du numéro de pensée."""
    # Pense 1/5
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Start",
        "next_thought_needed": True,
        "total_thoughts": 5,
        "branches": []
    })
    
    s1 = await client.call_tool("Start", thought_number=1, total_thoughts=5)
    assert s1.step_number == 1
    
    # Pense 3/5
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 3,
        "thought": "Middle",
        "next_thought_needed": True,
        "total_thoughts": 5,
        "branches": []
    })
    
    s3 = await client.call_tool("Middle", thought_number=3, total_thoughts=5)
    assert s3.step_number == 3
    
    # Pense 5/5 (fin)
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 5,
        "thought": "End",
        "next_thought_needed": False,
        "total_thoughts": 5,
        "branches": []
    })
    
    s5 = await client.call_tool("End", thought_number=5, total_thoughts=5)
    assert s5.step_number == 5
    assert s5.next_thought_needed is False


def test_is_available_true(client):
    """Test disponibilité quand connecté."""
    client._status = Mock(connected=True)
    assert client.is_available() is True


def test_is_available_false(client):
    """Test disponibilité quand déconnecté."""
    client._status = Mock(connected=False)
    assert client.is_available() is False


# Tests edge cases
@pytest.mark.asyncio
async def test_single_thought_workflow(client, mock_rpc):
    """Test workflow à une seule pensée."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Immediate solution",
        "next_thought_needed": False,
        "total_thoughts": 1,
        "branches": []
    })
    
    result = await client.call_tool("Quick issue", total_thoughts=1)
    
    assert result.total_thoughts == 1
    assert result.next_thought_needed is False


@pytest.mark.asyncio
async def test_many_thoughts_request(client, mock_rpc):
    """Test avec beaucoup de pensées (limite CPU)."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "thought_number": 1,
        "thought": "Start",
        "next_thought_needed": True,
        "total_thoughts": 20,
        "branches": []
    })
    
    result = await client.call_tool("Complex problem", total_thoughts=20)
    
    assert result.total_thoughts == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])