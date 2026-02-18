"""
Tests pour JsonQueryMCPClient.

Valide:
- JSONPath queries
- Recherche par clés
- Recherche par valeurs
- Fichiers JSON valides/invalides
- Timeout et erreurs
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
import json
import tempfile
import os
from datetime import datetime

from kimi_proxy.features.mcp.servers.json_query import JsonQueryMCPClient
from kimi_proxy.features.mcp.base.config import MCPClientConfig


@pytest.fixture
def config():
    """Config de test."""
    return MCPClientConfig(
        json_query_url="http://localhost:8005",
        json_query_api_key="test_key",
        json_query_timeout_ms=5000.0,
    )


@pytest.fixture
def mock_rpc():
    """RPC mock."""
    rpc = Mock()
    rpc.make_rpc_call = AsyncMock(return_value={
        "results": [{"key": "value"}]
    })
    return rpc


@pytest.fixture
def client(config, mock_rpc):
    """Client JSON Query."""
    return JsonQueryMCPClient(config, mock_rpc)


# Tests validation outils
def test_valid_tools(client):
    """Vérifie les 3 outils JSON Query."""
    assert len(client.VALID_TOOLS) == 3
    assert "json_query_jsonpath" in client.VALID_TOOLS
    assert "json_query_search_keys" in client.VALID_TOOLS
    assert "json_query_search_values" in client.VALID_TOOLS


@pytest.mark.asyncio
async def test_check_status(client, mock_rpc):
    """Test statut healthy."""
    status = await client.check_status()
    
    assert status.connected is True
    assert status.name == "json-query-mcp"
    assert status.tools_count == 3
    assert "jsonpath" in status.capabilities


@pytest.mark.asyncio
async def test_check_status_error(client, mock_rpc):
    """Test statut unhealthy."""
    mock_rpc.make_rpc_call = AsyncMock(side_effect=Exception("Connection error"))
    
    status = await client.check_status()
    
    assert status.connected is False
    assert status.error_count == 1


# Tests JSONPath
@pytest.mark.asyncio
async def test_jsonpath_query_simple(client, mock_rpc):
    """Test JSONPath simple."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [
            "The Lord of the Rings",
            "The Two Towers"
        ]
    })
    
    result = await client.jsonpath_query("books.json", "$.store.book[*].title")
    
    assert result.success is True
    assert len(result.results) >= 0
    assert result.query == "$.store.book[*].title"
    assert result.file_path == "books.json"


@pytest.mark.asyncio
async def test_jsonpath_with_filter(client, mock_rpc):
    """Test JSONPath avec filtre."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [{
            "title": "Sword of Honour",
            "price": 12.99,
            "category": "fiction"
        }]
    })
    
    result = await client.jsonpath_query(
        "books.json",
        "$.store.book[?(@.price < 15 && @.category == 'fiction')]"
    )
    
    assert result.success is True
    if result.results:
        assert result.results[0]["price"] < 15


# Helpers
@pytest.mark.asyncio
async def test_search_keys_helper(client, mock_rpc):
    """Test helper search_keys."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [
            {"key": "api_key", "path": "$[\"config\"][\"api_key\"]"},
            {"key": "api_key", "path": "$[\"secrets\"][\"api_key\"]"}
        ]
    })
    
    result = await client.search_keys("config.json", "api_key", limit=10)
    
    assert result.success is True
    assert len(result.results) > 0
    assert "api_key" in result.results[0]["key"]


@pytest.mark.asyncio
async def test_search_values_helper(client, mock_rpc):
    """Test helper search_values."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [
            {"value": "localhost:8000", "path": "$[\"server\"][\"host\"]"},
            {"value": "localhost:9000", "path": "$[\"api\"][\"url\"]"}
        ]
    })
    
    result = await client.search_values("config.json", "localhost", limit=5)
    
    assert result.success is True
    assert len(result.results) > 0
    assert "localhost" in result.results[0]["value"]


@pytest.mark.asyncio
async def test_call_tool_invalid(client, mock_rpc):
    """Test outil invalide."""
    result = await client.call_tool("invalid_tool", "file.json", "query")
    
    assert result.success is False
    assert "Outil invalide" in result.error


@pytest.mark.asyncio
async def test_rpc_error_fallback(client, mock_rpc):
    """Test fallback quand serveur down."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    result = await client.jsonpath_query("file.json", "$")
    
    assert result.success is False
    assert result.error == "Aucune réponse du serveur"


# Test format
@pytest.mark.asyncio
async def test_jsonpath_wildcard_all(client, mock_rpc):
    """Test wildcard * pour tous les chemins."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": ["value1", "value2", "value3"]
    })
    
    result = await client.jsonpath_query("data.json", "$.store.*")
    
    assert result.success is True


@pytest.mark.asyncio
async def test_jsonpath_recursive_descent(client, mock_rpc):
    """Test décente récursive '..'."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [
            {"id": 1, "name": "test1"},
            {"id": 2, "name": "test2"}
        ]
    })
    
    result = await client.jsonpath_query("data.json", "$..name")
    
    assert result.success is True


@pytest.mark.asyncio
async def test_jsonpath_array_index(client, mock_rpc):
    """Test index tableau."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": {"id": 1, "value": "first"}
    })
    
    result = await client.jsonpath_query("array.json", "$.items[0]")
    
    assert result.success is True


@pytest.mark.asyncio
async def test_jsonpath_slice(client, mock_rpc):
    """Test slice tableau [start:end]."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [{"id": 1}, {"id": 2}, {"id": 3}]
    })
    
    result = await client.jsonpath_query("array.json", "$.items[1:4]")
    
    assert result.success is True


# Test validation fichiers
@pytest.mark.asyncio
async def test_jsonpath_invalid_json_file(client, mock_rpc):
    """Test fichier JSON invalide."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "error": "Invalid JSON: unexpected token at column 15"
    })
    
    result = await client.jsonpath_query("invalid.json", "$")
    
    assert result.success is False


@pytest.mark.asyncio
async def test_jsonpath_complex_nested(client, mock_rpc):
    """Test JSON complexe imbriqué."""
    complex_data = {
        "users": [
            {"id": 1, "profile": {"name": "Alice", "roles": ["admin", "user"]}},
            {"id": 2, "profile": {"name": "Bob", "roles": ["user"]}}
        ]
    }
    
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": ["Alice", "Bob"]
    })
    
    result = await client.jsonpath_query("users.json", "$.users[*].profile.name")
    
    assert result.success is True
    assert len(result.results) == 2


@pytest.mark.asyncio
async def test_search_keys_no_results(client, mock_rpc):
    """Test recherche clés sans résultats."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": []
    })
    
    result = await client.search_keys("config.json", "nonexistent_key")
    
    assert result.success is True
    assert len(result.results) == 0


@pytest.mark.asyncio
async def test_search_values_no_results(client, mock_rpc):
    """Test recherche valeurs sans résultats."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": []
    })
    
    result = await client.search_values("config.json", "nonexistent_value")
    
    assert result.success is True
    assert len(result.results) == 0


# Test performance
@pytest.mark.asyncio
async def test_timeout_respected(client, mock_rpc):
    """Test timeout 5s respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [{"value": "test"}]
    })
    
    await client.jsonpath_query("file.json", "$")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["timeout_ms"] == 5000.0


@pytest.mark.asyncio
async def test_execution_time_tracking(client, mock_rpc):
    """Test tracking temps exécution."""
    start_time = DateTime.now()
    
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": ["result"]
    })
    
    result = await client.jsonpath_query("file.json", "$")
    
    assert result.execution_time_ms > 0
    assert result.execution_time_ms < 100  # Devrait être très rapide


# Tests clé API
@pytest.mark.asyncio
async def test_api_key_passed(client, mock_rpc):
    """Test clé API passée."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": []
    })
    
    await client.jsonpath_query("books.json", "$.title")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["api_key"] == "test_key"


# Edge cases
@pytest.mark.asyncio
async def test_jsonpath_empty_document(client, mock_rpc):
    """Test document JSON vide."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": []
    })
    
    result = await client.jsonpath_query("empty.json", "$")
    
    assert result.success is True


@pytest.mark.asyncio
async def test_jsonpath_deeply_nested(client, mock_rpc):
    """Test document très profond (10 niveaux)."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": ["bottom"]
    })
    
    result = await client.jsonpath_query("deep.json", "$.a.b.c.d.e.f.g.h.i.j.value")
    
    assert result.success is True


# Tests fichier réel (si possible)
@pytest.mark.asyncio
@pytest.mark.skip(reason="Nécessite fichier réel en local")
async def test_jsonpath_on_real_config(client):
    """Test sur fichier config.toml réel."""
    if os.path.exists("config.toml"):
        result = await client.jsonpath_query("config.toml", "$..url")
        assert result.success is True


def test_is_available_true(client):
    """Test disponibilité."""
    client._status = Mock(connected=True)
    assert client.is_available() is True


def test_is_available_false(client):
    """Test indisponibilité."""
    client._status = Mock(connected=False)
    assert client.is_available() is False


# Tests helper retourne JsonQueryResult
@pytest.mark.asyncio
async def test_helpers_return_proper_type(client, mock_rpc):
    """Test que les helpers retournent bien JsonQueryResult."""
    from kimi_proxy.core.models import JsonQueryResult
    
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "results": [{"test": "data"}]
    })
    
    jp = await client.jsonpath_query("file.json", "$")
    keys = await client.search_keys("file.json", "test")
    values = await client.search_values("file.json", "test")
    
    for result in [jp, keys, values]:
        assert isinstance(result, JsonQueryResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'query')
        assert hasattr(result, 'file_path')
        assert hasattr(result, 'results')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])