"""
Tests pour FileSystemMCPClient.

Valide:
- Les 25 outils de base (read, write, list, search, etc.)
- Helpers simplifiés
- Gestion des erreurs et validation
- Sécurité workspace
- Opérations batch
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from kimi_proxy.features.mcp.servers.filesystem import FileSystemMCPClient
from kimi_proxy.features.mcp.base.config import MCPClientConfig


@pytest.fixture
def config():
    """Config de test."""
    return MCPClientConfig(
        fast_filesystem_url="http://localhost:8004",
        fast_filesystem_api_key="test_key",
        fast_filesystem_timeout_ms=10000.0,
    )


@pytest.fixture
def mock_rpc():
    """RPC mock."""
    rpc = Mock()
    rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "content": "test content",
        "bytes_affected": 11
    })
    return rpc


@pytest.fixture
def client(config, mock_rpc):
    """Client FileSystem."""
    return FileSystemMCPClient(config, mock_rpc)


# Tests validation outils
def test_valid_tools_count(client):
    """Vérifie les 25 outils."""
    assert len(client.VALID_TOOLS) == 25
    assert "fast_read_file" in client.VALID_TOOLS
    assert "fast_write_file" in client.VALID_TOOLS
    assert "fast_search_code" in client.VALID_TOOLS
    assert "fast_edit_block" in client.VALID_TOOLS
    assert "fast_list_directory" in client.VALID_TOOLS


@pytest.mark.asyncio
async def test_check_status(client, mock_rpc):
    """Test statut."""
    status = await client.check_status()
    
    assert status.connected is True
    assert status.name == "fast-filesystem-mcp"
    assert status.tools_count == 25
    assert "file_operations" in status.capabilities


@pytest.mark.asyncio
async def test_check_status_error(client, mock_rpc):
    """Test statut error."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    status = await client.check_status()
    
    assert status.connected is False


@pytest.mark.asyncio
async def test_call_tool_invalid(client, mock_rpc):
    """Test outil invalide."""
    result = await client.call_tool("invalid_tool", {})
    
    assert result.success is False
    assert "Outil invalide" in result.error


@pytest.mark.asyncio
async def test_call_tool_valid(client, mock_rpc):
    """Test outil valide."""
    result = await client.call_tool("fast_read_file", {"path": "/tmp/test"})
    
    assert result.success is True
    assert result.path == "/tmp/test"
    assert result.operation == "fast_read_file"
    assert result.content == "test content"
    assert result.bytes_affected == 11
    
    # Vérifie appel RPC
    args = mock_rpc.make_rpc_call.call_args
    assert args[0][0] == "http://localhost:8004"
    assert args[1]["method"] == "fast_read_file"
    assert args[1]["params"]["path"] == "/tmp/test"


@pytest.mark.asyncio
async def test_call_tool_rpc_error(client, mock_rpc):
    """Test RPC error retourne 404."""
    mock_rpc.make_rpc_call = AsyncMock(return_value=None)
    
    result = await client.call_tool("fast_read_file", {"path": "/tmp/test"})
    
    assert result.success is False
    assert result.error == "Aucune réponse du serveur"


# Tests helpers simplifiés
@pytest.mark.asyncio
async def test_read_file_helper(client, mock_rpc):
    """Test helper read_file."""
    result = await client.read_file("/tmp/file.txt")
    
    assert result.success is True
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["path"] == "/tmp/file.txt"


@pytest.mark.asyncio
async def test_read_file_with_line_count(client, mock_rpc):
    """Test read_file avec limite lignes."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "content": "first\nsecond\nthird",
        "bytes_affected": 16
    })
    
    result = await client.read_file("/tmp/file.txt", line_count=10)
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["line_count"] == 10


@pytest.mark.asyncio
async def test_write_file_helper(client, mock_rpc):
    """Test helper write_file."""
    result = await client.write_file("/tmp/output.txt", "Hello World", append=True)
    
    assert result.success is True
    
    args = mock_rpc.make_rpc_call.call_args
    params = args[1]["params"]
    assert params["path"] == "/tmp/output.txt"
    assert params["content"] == "Hello World"
    assert params["append"] is True


@pytest.mark.asyncio
async def test_write_file_overwrite(client, mock_rpc):
    """Test write_file overwrite (default)."""
    result = await client.write_file("/tmp/output.txt", "New content", append=False)
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["params"]["append"] is False


@pytest.mark.asyncio
async def test_search_code_helper(client, mock_rpc):
    """Test helper search_code."""
    result = await client.search_code("/src", "TODO.*", max_results=50)
    
    args = mock_rpc.make_rpc_call.call_args
    params = args[1]["params"]
    assert params["path"] == "/src"
    assert params["pattern"] == "TODO.*"
    assert params["max_results"] == 50
    assert args[1]["method"] == "fast_search_code"


@pytest.mark.asyncio
async def test_list_directory_helper(client, mock_rpc):
    """Test helper list_directory."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "files": ["file1.txt", "file2.txt"],
        "directories": ["dir1", "dir2"]
    })
    
    result = await client.list_directory("/home", recursive=True)
    
    args = mock_rpc.make_rpc_call.call_args
    params = args[1]["params"]
    assert params["path"] == "/home"
    assert params["recursive"] is True
    assert params.get("show_hidden", None) is None  # Default None


# Tests opérations fichiers
@pytest.mark.asyncio
async def test_copy_file(client, mock_rpc):
    """Test copie fichier."""
    await client.call_tool("fast_copy_file", {
        "source": "/src/file.txt",
        "destination": "/dst/file.txt"
    })
    
    args = mock_rpc.make_rpc_call.call_args
    params = args[1]["params"]
    assert params["source"] == "/src/file.txt"
    assert params["destination"] == "/dst/file.txt"


@pytest.mark.asyncio
async def test_move_file(client, mock_rpc):
    """Test déplacement fichier."""
    await client.call_tool("fast_move_file", {
        "source": "/tmp/temp.txt",
        "destination": "/home/temp.txt",
        "backup_if_exists": True
    })


@pytest.mark.asyncio
async def test_delete_file(client, mock_rpc):
    """Test suppression fichier."""
    await client.call_tool("fast_delete_file", {
        "path": "/tmp/old.txt",
        "recursive": False,
        "confirm_delete": True
    })


@pytest.mark.asyncio
async def test_edit_block(client, mock_rpc):
    """Test édition bloc précis."""
    await client.call_tool("fast_edit_block", {
        "path": "/config.ini",
        "old_text": "old_value = 123",
        "new_text": "new_value = 456",
        "backup": True
    })


@pytest.mark.asyncio
async def test_safe_edit(client, mock_rpc):
    """Test édition safe (confirmation)."""
    await client.call_tool("fast_safe_edit", {
        "path": "/tmp/test.py",
        "old_text": "def old(): pass",
        "new_text": "def new(): print('Hello')",
        "require_confirmation": True
    })


@pytest.mark.asyncio
async def test_list_allowed_directories(client, mock_rpc):
    """Test listing répertoires autorisés."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "directories": ["/home", "/tmp", "/var/log"]
    })
    
    result = await client.call_tool("fast_list_allowed_directories", {})
    
    assert result.success is True


@pytest.mark.asyncio
async def test_get_file_info(client, mock_rpc):
    """Test info fichier."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "size": 1024,
        "modified": "2026-02-18T12:00:00",
        "permissions": "rw-r--r--"
    })
    
    result = await client.call_tool("fast_get_file_info", {"path": "/tmp/file.txt"})
    
    assert result.success is True
    assert result.bytes_affected == 1024


@pytest.mark.asyncio
async def test_get_directory_tree(client, mock_rpc):
    """Test tree répertoire."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "tree": {
            "name": "/src",
            "children": [{"name": "main.py", "type": "file"}]
        }
    })
    
    result = await client.call_tool("fast_get_directory_tree", {
        "path": "/src",
        "show_hidden": False,
        "include_files": True
    })


@pytest.mark.asyncio
async def test_get_disk_usage(client, mock_rpc):
    """Test usage disque."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "total": 1000000000,
        "used": 500000000,
        "available": 500000000,
        "usage_percent": 50
    })
    
    result = await client.call_tool("fast_get_disk_usage", {"path": "/"})


@pytest.mark.asyncio
async def test_find_large_files(client, mock_rpc):
    """Test fichiers volumineux."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "large_files": [
            {"path": "/logs/big.log", "size": 1000000}
        ]
    })
    
    result = await client.call_tool("fast_find_large_files", {
        "path": "/logs",
        "min_size": "100MB"
    })


@pytest.mark.asyncio
async def test_extract_lines(client, mock_rpc):
    """Test extraction lignes."""
    await client.call_tool("fast_extract_lines", {
        "path": "/logs/app.log",
        "start_line": 10,
        "end_line": 20,
        "pattern": "ERROR"
    })


@pytest.mark.asyncio
async def test_batch_operations(client, mock_rpc):
    """Test opérations batch."""
    await client.call_tool("fast_batch_file_operations", {
        "operations": [
            {"operation": "delete", "source": "/tmp/a.txt"},
            {"operation": "copy", "source": "/tmp/b.txt", "destination": "/home/b.txt"}
        ],
        "dry_run": True
    })


@pytest.mark.asyncio
async def test_compress_files(client, mock_rpc):
    """Test compression fichiers."""
    await client.call_tool("fast_compress_files", {
        "paths": ["/logs/*.log", "/tmp/*.tmp"],
        "output_path": "/archive/logs.zip",
        "format": "zip"
    })


@pytest.mark.asyncio
async def test_extract_archive(client, mock_rpc):
    """Test extraction archive."""
    await client.call_tool("fast_extract_archive", {
        "archive_path": "/archive/data.zip",
        "extract_to": "/data",
        "extract_specific": ["file1.txt", "file2.txt"]
    })


# Validation sécurité workspace
@pytest.mark.asyncio
async def test_workspace_security(client, mock_rpc):
    """Test que le workspace est correctement validé."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": False,
        "error": "Access denied: path not in allowed workspace"
    })
    
    result = await client.call_tool("fast_read_file", {"path": "/etc/passwd"})
    
    assert result.success is False
    assert "Access denied" in result.error


def test_is_available_true(client):
    """Test disponibilité."""
    client._status = Mock(connected=True)
    assert client.is_available() is True


def test_is_available_false(client):
    """Test indisponibilité."""
    client._status = Mock(connected=False)
    assert client.is_available() is False


# Tests timeout
@pytest.mark.asyncio
async def test_timeout_respected(client, mock_rpc):
    """Test timeout 10s respecté."""
    mock_rpc.make_rpc_call = AsyncMock(return_value={
        "success": True,
        "content": "test"
    })
    
    await client.read_file("/tmp/test")
    
    args = mock_rpc.make_rpc_call.call_args
    assert args[1]["timeout_ms"] == 10000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])