"""
Tests unitaires pour CompressionMCPClient.

Vérifie :
- Compression algorithmes (context_aware, zlib, none)
- Fallback zlib en cas d'échec serveur
- Décompression (zlib et context_aware)
- Calcul de ratio et qualité
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime

from kimi_proxy.features.mcp.servers.compression import CompressionMCPClient
from kimi_proxy.features.mcp.base.config import MCPClientConfig
from kimi_proxy.features.mcp.base.rpc import MCPRPCClient
from kimi_proxy.core.tokens import count_tokens_text


@pytest.fixture
def mock_config():
    """Config de test."""
    return MCPClientConfig(
        compression_url="http://localhost:8001",
        compression_api_key="test_key",
        compression_timeout_ms=5000.0,
    )


@pytest.fixture
def mock_rpc():
    """RPC client mock."""
    rpc = Mock(spec=MCPRPCClient)
    rpc.make_rpc_call = AsyncMock(return_value={})
    return rpc


@pytest.fixture
def client(mock_config, mock_rpc):
    """Client Compression avec mocks."""
    return CompressionMCPClient(mock_config, mock_rpc)


@pytest.mark.asyncio
async def test_check_status_healthy(client, mock_rpc):
    """Test statut compression healthy."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "status": "healthy",
        "capabilities": ["zlib", "context_aware"]
    })
    
    status = await client.check_status()
    
    assert status.connected is True
    assert status.name == "context-compression-mcp"
    assert "zlib" in status.capabilities
    assert status.latency_ms > 0


@pytest.mark.asyncio
async def test_check_status_error(client, mock_rpc):
    """Test statut compression avec erreur."""
    mock_rpc.make_rpc_call = AsyncMock(side_effect=Exception("Connection failed"))
    
    status = await client.check_status()
    
    assert status.connected is False
    assert status.error_count == 1
    assert status.capabilities == []


@pytest.mark.asyncio
async def test_compress_content_success(client, mock_rpc):
    """Test compression réussie."""
    original = "This is a test of the compression system. " * 10
    compressed_content = "Compressed version"
    
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "compressed": compressed_content,
        "algorithm": "context_aware",
        "quality_score": 0.85
    })
    
    result = await client.compress_content(
        original,
        algorithm="context_aware",
        target_ratio=0.5
    )
    
    original_tokens = count_tokens_text(original)
    compressed_tokens = count_tokens_text(compressed_content)
    
    assert result.original_tokens == original_tokens
    assert result.compressed_tokens == compressed_tokens
    assert result.compression_ratio > 0
    assert result.algorithm == "context_aware"
    assert result.compressed_content == compressed_content
    assert result.quality_score == 0.85


@pytest.mark.asyncio
async def test_compress_content_server_error_fallback(client, mock_rpc):
    """Test compression avec erreur serveur → fallback zlib."""
    original = "Short text"
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)  # Erreur
    
    # Spy sur _fallback_compression
    with patch.object(client, '_fallback_compression', new_callable=AsyncMock) as mock_fallback:
        mock_fallback.return_value = Mock(
            original_tokens=10,
            compressed_tokens=7,
            compression_ratio=0.3,
            algorithm="zlib_fallback_from_context_aware",
            compressed_content="ZmFrZSBjb21wcmVzc2Vk",  # base64
            quality_score=0.7
        )
        
        result = await client.compress_content(original, algorithm="context_aware")
        
        # Vérifie que le fallback a été appelé
        mock_fallback.assert_called_once()
        assert "zlib_fallback" in result.algorithm


@pytest.mark.asyncio
async def test_fallback_compression_simulated(client):
    """Test fallback zlib avec simulation 30%."""
    original = "This is a long text that will be compressed. " * 20
    original_tokens = count_tokens_text(original)
    start_time = datetime.now()
    
    result = await client._fallback_compression(
        original,
        original_tokens,
        start_time
    )
    
    # Vérifie la simulation
    expected_compressed_tokens = int(original_tokens * 0.7)
    assert result.compressed_tokens == expected_compressed_tokens
    assert result.compression_ratio == 0.3
    assert "zlib_fallback" in result.algorithm
    assert result.quality_score == 0.7
    assert result.decompression_time_ms > 0


@pytest.mark.asyncio
async def test_fallback_compression_total_failure(client):
    """Test fallback total échec (retourne contenu original)."""
    original = "Test"
    original_tokens = count_tokens_text(original)
    
    # Corrupt les données pour forcer l'échec zlib
    with patch('zlib.compress', side_effect=Exception("Zlib error")):
        start_time = datetime.now()
        result = await client._fallback_compression(
            original,
            original_tokens,
            start_time
        )
    
    assert result.compression_ratio == 0.0
    assert result.algorithm == "none"
    assert result.compressed_content == original
    assert result.quality_score == 0.0


@pytest.mark.asyncio
async def test_decompress_zlib(client):
    """Test décompression zlib réussie."""
    original = "Hello World Data"
    compressed = base64.b64encode(zlib.compress(original.encode())).decode()
    
    decompressed = await client.decompress(compressed, algorithm="zlib")
    
    assert decompressed == original


@pytest.mark.asyncio
async def test_decompress_context_aware_fallback_to_zlib(client, mock_rpc):
    """Test décompression context_aware fallback vers zlib."""
    original = "Data to decompress"
    compressed = base64.b64encode(zlib.compress(original.encode())).decode()
    
    # Mock make_rpc_call pour simuler erreur
    mock_rpc.make_rpc_call = AsyncMock(side_effect=Exception("Server down"))
    
    decompressed = await client.decompress(compressed, algorithm="context_aware")
    
    # Fallback vers zlib
    assert decompressed == original


@pytest.mark.asyncio
async def test_decompress_no_compression(client):
    """Test décompression quand algorithm=none."""
    content = "Plain text content"
    
    decompressed = await client.decompress(content, algorithm="none")
    
    assert decompressed == content


@pytest.mark.asyncio
async def test_decompress_zlib_failure(client):
    """Test décompression zlib avec données invalides."""
    invalid_data = "Not valid base64!"
    
    decompressed = await client.decompress(invalid_data, algorithm="zlib")
    
    # Fallback: retourne les données brutes
    assert decompressed == invalid_data


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


# Tests de calcul de ratio
@pytest.mark.parametrize("original_tokens,compressed_tokens,expected_ratio", [
    (100, 70, 0.3),
    (1000, 500, 0.5),
    (0, 0, 0.0),
    (100, 0, 1.0),
])
def test_compression_ratio_calculation(original_tokens, compressed_tokens, expected_ratio):
    """Test calcul ratio compression."""
    if original_tokens > 0:
        ratio = (original_tokens - compressed_tokens) / original_tokens
        assert round(ratio, 2) == round(expected_ratio, 2)


# Tests de paramètres RPC
@pytest.mark.asyncio
async def test_compress_rpc_parameters(client, mock_rpc):
    """Test paramètres envoyés à RPC."""
    content = "Test content"
    mock_rpc.make_rpc_call = AsyncMock(return_value={})
    
    await client.compress_content(content, algorithm="context_aware", target_ratio=0.5)
    
    call_args = mock_rpc.make_rpc_call.call_args
    
    assert call_args[0][0] == "http://localhost:8001"
    assert call_args[1]["method"] == "compress"
    assert call_args[1]["timeout_ms"] == 5000.0
    assert call_args[1]["api_key"] == "test_key"
    
    params = call_args[1]["params"]
    assert params["content"] == content
    assert params["algorithm"] == "context_aware"
    assert params["target_ratio"] == 0.5


@pytest.mark.asyncio
async def test_decompress_rpc_parameters(client, mock_rpc):
    """Test paramètres de décompression RPC."""
    compressed = "compressed data"
    mock_rpc.make_rpc_call = AsyncMock(return_value={"content": "original"})
    
    await client.decompress(compressed, algorithm="context_aware")
    
    call_args = mock_rpc.make_rpc_call.call_args
    
    assert call_args[0][0] == "http://localhost:8001"
    assert call_args[1]["method"] == "decompress"


# Tests performance
@pytest.mark.asyncio
async def test_compression_performance_small(client, mock_rpc):
    """Test performance sur petit texte."""
    small_text = "Hello " * 10
    
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "compressed": "Compressed",
        "quality_score": 0.9
    })
    
    result = await client.compress_content(small_text)
    
    # Vérifie que les tokens sont comptés correctement
    assert result.original_tokens > 0


@pytest.mark.asyncio
async def test_compression_performance_large(client, mock_rpc):
    """Test performance sur grand texte."""
    large_text = "This is a long text. " * 1000
    
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "compressed": large_text[:100],  # Simule compression
        "quality_score": 0.85
    })
    
    result = await client.compress_content(large_text)
    
    # Vérifie que le ratio est calculé
    assert result.compression_ratio >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])