"""
Tests unitaires pour QdrantMCPClient.

Vérifie:
- Gestion des erreurs avec retry
- Logique de cache statut
- Construction des paramètres RPC
- Fallbacks appropriés
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime

from kimi_proxy.features.mcp.servers.qdrant import QdrantMCPClient
from kimi_proxy.features.mcp.base.config import MCPClientConfig
from kimi_proxy.features.mcp.base.rpc import MCPRPCClient
from kimi_proxy.core.models import MCPCluster


@pytest.fixture
def mock_config():
    """Config de test."""
    return MCPClientConfig(
        qdrant_url="http://localhost:6333",
        qdrant_api_key="test_key",
        qdrant_collection="test_collection",
        search_timeout_ms=50.0,
    )


@pytest.fixture
def mock_rpc():
    """RPC client mock."""
    rpc = Mock(spec=MCPRPCClient)
    rpc._get_client = AsyncMock(return_value=Mock(
        get=AsyncMock(return_value=Mock(status_code=200))
    ))
    return rpc


@pytest.fixture
def client(mock_config, mock_rpc):
    """Client Qdrant avec mocks."""
    return QdrantMCPClient(mock_config, mock_rpc)


# Tests de statut
@pytest.mark.asyncio
async def test_check_status_healthy(client, mock_rpc):
    """Test statut Qdrant healthy."""
    mock_http = Mock()
    mock_http.get = AsyncMock(return_value=Mock(status_code=200))
    mock_rpc._get_client = AsyncMock(return_value=mock_http)
    
    # Mock make_rpc_call pour la méthode health
    mock_rpc.make_rpc_call = AsyncMock(return_value={"status": "ok"})
    
    status = await client.check_status()
    
    assert status.connected is True
    assert status.name == "qdrant-mcp"
    assert "semantic_search" in status.capabilities


@pytest.mark.asyncio
async def test_check_status_unhealthy(client, mock_rpc):
    """Test statut Qdrant unhealthy."""
    mock_http = Mock()
    mock_http.get = AsyncMock(side_effect=Exception("Connection failed"))
    mock_rpc._get_client = AsyncMock(return_value=mock_http)
    
    status = await client.check_status()
    
    assert status.connected is False
    assert status.error_count == 1


@pytest.mark.asyncio
async def test_check_status_cache_ttl(client, mock_rpc):
    """Test cache TTL de 30 secondes."""
    # Première appel
    mock_rpc._get_client = AsyncMock(return_value=Mock(get=AsyncMock(return_value=Mock(status_code=200))))
    
    status1 = await client.check_status()
    time1 = client._status_check_time
    
    # Deuxième appel immédiat (devrait utiliser le cache)
    status2 = await client.check_status()
    time2 = client._status_check_time
    
    # Même objet statut et même temps
    assert status1 is status2
    assert time1 == time2


# Tests de recherche
@pytest.mark.asyncio
async def test_search_similar_success(client, mock_rpc):
    """Test recherche sémantique réussie."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "hits": [
            {
                "id": "vec1",
                "score": 0.95,
                "payload": {
                    "preview": "Preview 1",
                    "content": "Full content 1",
                    "metadata": {"key": "value"}
                }
            },
            {
                "id": "vec2",
                "score": 0.78,
                "payload": {
                    "preview": "Preview 2",
                    "content": "Full content 2",
                    "metadata": {}
                }
            }
        ]
    })
    
    results = await client.search_similar("test query", limit=2, score_threshold=0.7)
    
    assert len(results) == 2
    assert results[0].id == "vec1"
    assert results[0].score == 0.95
    assert results[0].content_preview == "Preview 1"
    assert results[1].id == "vec2"


@pytest.mark.asyncio
async def test_search_similar_empty(client, mock_rpc):
    """Test recherche sans résultats."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    results = await client.search_similar("no results query")
    
    assert results == []


@pytest.mark.asyncio
async def test_search_similar_rpc_error(client, mock_rpc):
    """Test recherche avec erreur RPC (fallback)."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    results = await client.search_similar("error query")
    
    # Fallback: retourne liste vide
    assert results == []


# Tests de stockage
@pytest.mark.asyncio
async def test_store_vector_success(client, mock_rpc):
    """Test stockage vecteur réussi."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"id": "vec_123"})
    
    vector_id = await client.store_vector(
        "Test content",
        memory_type="episodic",
        metadata={"key": "value"}
    )
    
    assert vector_id == "vec_123"
    
    # Vérifie les paramètres de l'appel RPC
    mock_rpc.make_rpc_call.assert_called_once()
    call_args = mock_rpc.make_rpc_call.call_args
    assert call_args[0][0] == "http://localhost:6333"
    assert call_args[1]["method"] == "upsert"
    assert call_args[1]["timeout_ms"] == 1000.0
    
    # Vérifie les points envoyés
    params = call_args[1]["params"]
    assert "points" in params
    assert params["points"][0]["payload"]["content"] == "Test content"
    assert params["points"][0]["payload"]["type"] == "episodic"


@pytest.mark.asyncio
async def test_store_vector_rpc_error(client, mock_rpc):
    """Test stockage avec erreur RPC."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    vector_id = await client.store_vector("Test content")
    
    # Fallback: retourne None
    assert vector_id is None


# Tests de détection de redondance
@pytest.mark.asyncio
async def test_find_redundant_found(client, mock_rpc):
    """Test détection de mémoires redondantes."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "hits": [
            {"id": "vec1", "score": 0.95, "payload": {"content": "Similar content"}},
            {"id": "vec2", "score": 0.88, "payload": {"content": "Also similar"}},
            {"id": "vec3", "score": 0.70, "payload": {"content": "Less similar"}}
        ]
    })
    
    redundant_ids = await client.find_redundant("test content", similarity_threshold=0.85)
    
    # Deux IDs au-dessus du seuil de 0.85
    assert len(redundant_ids) == 2
    assert "vec1" in redundant_ids
    assert "vec2" in redundant_ids
    assert "vec3" not in redundant_ids  # Score trop bas


@pytest.mark.asyncio
async def test_find_redundant_empty(client, mock_rpc):
    """Test détection sans redondances."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "hits": [{"id": "vec1", "score": 0.80, "payload": {}}]
    })
    
    redundant_ids = await client.find_redundant("content", similarity_threshold=0.85)
    
    # Aucun au-dessus du seuil
    assert len(redundant_ids) == 0


# Tests de clustering
@pytest.mark.asyncio
async def test_cluster_memories_success(client, mock_rpc):
    """Test clustering réussi."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "clusters": [
            {
                "id": "cluster1",
                "center_id": "center1",
                "point_ids": ["vec1", "vec2", "vec3"],
                "cohesion": 0.92,
                "topic": "Backend API"
            },
            {
                "id": "cluster2",
                "center_id": "center2",
                "point_ids": ["vec4", "vec5"],
                "cohesion": 0.88,
                "topic": "Database Schema"
            }
        ]
    })
    
    clusters = await client.cluster_memories(session_id=42, min_cluster_size=3)
    
    assert len(clusters) == 2
    assert clusters[0].id == "cluster1"
    assert len(clusters[0].memory_ids) == 3
    assert clusters[0].cohesion_score == 0.92
    assert clusters[0].topic_label == "Backend API"


@pytest.mark.asyncio
async def test_cluster_memories_failure(client, mock_rpc):
    """Test clustering avec erreur."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    clusters = await client.cluster_memories(session_id=42)
    
    # Fallback: retourne liste vide
    assert clusters == []


# Tests de disponibilité
def test_is_available_true(client):
    """Test is_available quand connecté."""
    client._status = Mock(connected=True)
    assert client.is_available() is True


def test_is_available_false(client):
    """Test is_available quand déconnecté."""
    client._status = Mock(connected=False)
    assert client.is_available() is False


def test_is_available_no_status(client):
    """Test is_available sans statut."""
    client._status = None
    assert client.is_available() is False


# Tests de génération d'ID
@pytest.mark.parametrize("content,memory_type,expected_prefix", [
    ("test content 1", "episodic", "episodic_"),
    ("test content 2", "frequent", "frequent_"),
    ("test content 3", "semantic", "semantic_"),
])
def test_generate_vector_id(client, content, memory_type, expected_prefix):
    """Test génération ID stable basé sur hash."""
    id1 = client._generate_vector_id(content, memory_type)
    id2 = client._generate_vector_id(content, memory_type)
    
    # Même contenu = même ID
    assert id1 == id2
    assert id1.startswith(expected_prefix)
    assert len(id1) > len(expected_prefix)


# Tests de timeout
@pytest.mark.asyncio
async def test_search_timeout_respected(client, mock_rpc):
    """Test que le timeout de recherche est respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"hits": []})
    
    await client.search_similar("test query")
    
    # Vérifie que le timeout passé est bien 50ms
    call_args = mock_rpc.make_rpc_call.call_args
    assert call_args[1]["timeout_ms"] == 50.0


@pytest.mark.asyncio
async def test_cluster_timeout_respected(client, mock_rpc):
    """Test que le timeout de clustering est respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={"clusters": []})
    
    await client.cluster_memories(42)
    
    call_args = mock_rpc.make_rpc_call.call_args
    assert call_args[1]["timeout_ms"] == 2000.0


@pytest.mark.asyncio
async def test_store_timeout_respected(client, mock_rpc):
    """Test que le timeout de stockage est respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    await client.store_vector("content")
    
    call_args = mock_rpc.make_rpc_call.call_args
    assert call_args[1]["timeout_ms"] == 1000.0


# Tests de passage API key
@pytest.mark.asyncio
async def test_api_key_passed_to_rpc(client, mock_rpc):
    """Test que l'API key est correctement passée aux appels."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    await client.store_vector("content")
    
    call_args = mock_rpc.make_rpc_call.call_args
    assert call_args[1]["api_key"] == "test_key"
