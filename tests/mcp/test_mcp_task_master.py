"""
Tests pour TaskMasterMCPClient.

Valide:
- Les 14 outils disponibles
- Workflow complet (parse_prd → expand_task → get_next_task)
- Gestion des statuts et des tâches
- Stats par statut
- Configuration projet
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime

from kimi_proxy.features.mcp.servers.task_master import TaskMasterMCPClient
from kimi_proxy.features.mcp.base.config import MCPClientConfig


@pytest.fixture
def config():
    """Config de test."""
    return MCPClientConfig(
        task_master_url="http://localhost:8002",
        task_master_api_key="test_key",
        task_master_timeout_ms=30000.0,
    )


@pytest.fixture
def mock_rpc():
    """RPC mock."""
    rpc = Mock()
    rpc.make_rpc_call = AsyncMock(return_value={})
    return rpc


@pytest.fixture
async def client(config, mock_rpc):
    """Client Task Master."""
    return TaskMasterMCPClient(config, mock_rpc)


# Tests de validation des outils
def test_valid_tools_list(client):
    """Vérifie les 14 outils valides."""
    assert len(client.VALID_TOOLS) == 14
    assert "get_tasks" in client.VALID_TOOLS
    assert "parse_prd" in client.VALID_TOOLS
    assert "expand_task" in client.VALID_TOOLS
    assert "set_task_status" in client.VALID_TOOLS


@pytest.mark.asyncio
async def test_check_status_healthy(client, mock_rpc):
    """Test statut healthy."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "tasks": [{"id": 1, "title": "Test"}]
    })
    
    status = await client.check_status()
    
    assert status.connected is True
    assert status.tools_count == 14
    assert "task_management" in status.capabilities


@pytest.mark.asyncio
async def test_check_status_unhealthy(client, mock_rpc):
    """Test statut unhealthy."""
    mock_rpc.make_rpc_call = AsyncMock(side_effect=Exception("Connection failed"))
    
    status = await client.check_status()
    
    assert status.connected is False
    assert status.error_count == 1


# Tests appels outils
@pytest.mark.asyncio
async def test_call_tool_invalid(client, mock_rpc):
    """Test appel outil invalide."""
    result = await client.call_tool("invalid_tool", {})
    
    assert "error" in result
    assert "get_tasks" in result["valid_tools"]


@pytest.mark.asyncio
async def test_call_tool_valid(client, mock_rpc):
    """Test appel outil valide."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"result": "ok"})
    
    result = await client.call_tool("get_tasks", {"limit": 10})
    
    mock_rpc.make_rpc_call.assert_called_once()
    args = mock_rpc.make_rpc_call.call_args
    assert args[0][0] == "http://localhost:8002"
    assert args[1]["method"] == "get_tasks"
    assert args[1]["params"]["limit"] == 10


# Tests get_tasks
@pytest.mark.asyncio
async def test_get_tasks_no_filter(client, mock_rpc):
    """Test get_tasks sans filtre."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "tasks": [
            {"id": 1, "title": "Task 1", "status": "pending"},
            {"id": 2, "title": "Task 2", "status": "in-progress"},
        ]
    })
    
    tasks = await client.get_tasks()
    
    assert len(tasks) == 2
    assert tasks[0].id == 1
    assert tasks[0].status == "pending"
    assert tasks[1].id == 2
    assert tasks[1].status == "in-progress"


@pytest.mark.asyncio
async def test_get_tasks_with_filter(client, mock_rpc):
    """Test get_tasks avec filtre status."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "tasks": [{"id": 1, "title": "Pending Task", "status": "pending"}]
    })
    
    tasks = await client.get_tasks(status_filter="pending")
    
    assert len(tasks) == 1
    assert tasks[0].status == "pending"
    
    # Vérifie filtre passé
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_tasks_empty(client, mock_rpc):
    """Test get_tasks avec résultat vide."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    tasks = await client.get_tasks()
    
    assert tasks == []


# Tests get_next_task
@pytest.mark.asyncio
async def test_get_next_task(client, mock_rpc):
    """Test get_next_task."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "task": {"id": 1, "title": "Next Task", "status": "pending", "priority": "high"}
    })
    
    task = await client.get_next_task()
    
    assert task is not None
    assert task.id == 1
    assert task.priority == "high"


@pytest.mark.asyncio
async def test_get_next_task_none(client, mock_rpc):
    """Test get_next_task sans résultat."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    task = await client.get_next_task()
    
    assert task is None


# Tests stats
@pytest.mark.asyncio
async def test_get_stats(client, mock_rpc):
    """Test calcul stats par status."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "tasks": [
            {"id": 1, "status": "pending"},
            {"id": 2, "status": "in-progress"},
            {"id": 3, "status": "done"},
            {"id": 4, "status": "done"},
            {"id": 5, "status": "blocked"},
            {"id": 6, "status": "deferred"},
        ]
    })
    
    stats = await client.get_stats()
    
    assert stats.total_tasks == 6
    assert stats.pending == 1
    assert stats.in_progress == 1
    assert stats.done == 2
    assert stats.blocked == 1
    assert stats.deferred == 1


@pytest.mark.asyncio
async def test_get_stats_empty(client, mock_rpc):
    """Test stats avec liste vide."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    stats = await client.get_stats()
    
    assert stats.total_tasks == 0


# Tests workflow PRD
@pytest.mark.asyncio
async def test_parse_prd_workflow(client, mock_rpc):
    """Test workflow parse_prd complet."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "tasks_created": 5,
        "file": ".taskmaster/tasks.json"
    })
    
    result = await client.parse_prd(
        input_file="docs/prd.md",
        research_enabled=True,
        num_tasks=5
    )
    
    assert result["success"] is True
    assert result["tasks_created"] == 5
    
    # Vérifie les paramètres
    args = mock_rpc.make_rpc_call.call_args
    assert args[0][0] == "http://localhost:8002"
    assert args[1]["method"] == "parse_prd"
    assert args[1]["params"]["input"] == "docs/prd.md"
    assert args[1]["params"]["research"] is True
    assert args[1]["params"]["numTasks"] == 5


# Tests expand_task
@pytest.mark.asyncio
async def test_expand_task(client, mock_rpc):
    """Test expansion tâche."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "id": 1,
        "title": "Main Task",
        "subtasks": [
            {"id": 1.1, "title": "Subtask 1"},
            {"id": 1.2, "title": "Subtask 2"}
        ]
    })
    
    result = await client.expand_task(
        task_id=1,
        num_subtasks=5,
        prompt="Implémenter avec FastAPI"
    )
    
    assert result["id"] == 1
    assert "subtasks" in result
    assert len(result["subtasks"]) == 2
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["id"] == 1
    assert args[1]["params"]["num"] == "5"
    assert args[1]["params"]["prompt"] == "Implémenter avec FastAPI"


@pytest.mark.asyncio
async def test_expand_task_no_prompt(client, mock_rpc):
    """Test expansion sans prompt."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    result = await client.expand_task(task_id=1)
    
    args = mock_rpc.make_rpc_call.call_args
    assert "prompt" not in args[1]["params"]


# Tests initialize_project
@pytest.mark.asyncio
async def test_initialize_project(client, mock_rpc):
    """Test initialisation projet."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"initialized": True})
    
    result = await client.initialize_project("/path/to/project")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["projectRoot"] == "/path/to/project"
    assert args[1]["params"]["initGit"] is True


# Tests set_task_status
@pytest.mark.asyncio
async def test_set_task_status(client, mock_rpc):
    """Test mise à jour statut tâche."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"updated": True})
    
    result = await client.set_task_status(1, "in-progress")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["id"] == "1"
    assert args[1]["params"]["status"] == "in-progress"


@pytest.mark.asyncio
async def test_set_subtask_status(client, mock_rpc):
    """Test mise à jour statut sous-tâche."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"updated": True})
    
    result = await client.set_task_status(1, "done", subtask_id="2")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["id"] == "1,2"


# Tests de timeout
@pytest.mark.asyncio
async def test_timeout_respected(client, mock_rpc):
    """Test timeout à 30s respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    await client.call_tool("get_tasks", {})
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["timeout_ms"] == 30000.0


# Tests disponibilité
def test_is_available_true(client):
    """Test disponibilité quand connecté."""
    client._status = Mock(connected=True)
    assert client.is_available() is True


def test_is_available_false(client):
    """Test disponibilité quand déconnecté."""
    client._status = Mock(connected=False)
    assert client.is_available() is False


# Tests workflow complet
@pytest.mark.asyncio
async def test_complet_prd_workflow(client, mock_rpc):
    """
    Workflow complet: parse_prd → get_tasks → expand_task → get_stats
    """
    # Étape 1: parse_prd
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "tasks_created": 3
    })
    
    prd_result = await client.parse_prd("prd.txt")
    assert prd_result["success"] is True
    
    # Étape 2: get_tasks
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "tasks": [
            {"id": 1, "status": "pending"},
            {"id": 2, "status": "pending"}
        ]
    })
    
    tasks = await client.get_tasks()
    assert len(tasks) == 2
    
    # Étape 3: expand_task
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "id": 1,
        "title": "API Implementation",
        "subtasks": [{"id": 1.1, "title": "Setup"}]
    })
    
    expanded = await client.expand_task(1, 5)
    assert "subtasks" in expanded
    
    # Étape 4: stats
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "tasks": [
            {"id": 1, "status": "pending"},
            {"id": 2, "status": "in-progress"}
        ]
    })
    
    stats = await client.get_stats()
    assert stats.total_tasks == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])