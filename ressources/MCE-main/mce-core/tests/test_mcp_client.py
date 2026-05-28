"""
MCE — MCP Client Tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.mcp_client import MCPClient
from schemas.json_rpc import JsonRpcResponse, JsonRpcError
from schemas.mce_config import UpstreamServer


class TestMCPClientBasics:
    def test_no_servers_configured(self):
        client = MCPClient()
        assert client._servers == {}

    def test_register_tool(self):
        client = MCPClient([UpstreamServer(name="fs", url="http://localhost:3001")])
        client.register_tool("read_file", "fs")
        assert client._tool_to_server["read_file"] == "fs"

    def test_find_server_fallback(self):
        client = MCPClient([UpstreamServer(name="fs", url="http://localhost:3001")])
        # No tool registered, but servers exist
        server = client._find_server_for_tool("unknown_tool")
        assert server is not None
        assert server.name == "fs"

    def test_find_server_no_servers(self):
        client = MCPClient()
        assert client._find_server_for_tool("unknown_tool") is None


class TestMCPClientErrors:
    def test_call_tool_no_server(self):
        client = MCPClient()
        # Need to start client so _client is not None
        import asyncio
        asyncio.run(client.start())
        resp = asyncio.run(client.call_tool("unknown", {}))
        assert resp.error is not None
        assert resp.error.code == -32601
        asyncio.run(client.stop())

    def test_error_response_passthrough(self):
        # Construct a mock upstream error response
        err = JsonRpcError(code=-32000, message="Upstream died")
        resp = JsonRpcResponse(error=err)
        assert resp.error.message == "Upstream died"


class TestInferDomain:
    def test_infer_domain(self):
        client = MCPClient()
        assert client._infer_domain("read_file", "filesystem") == "filesystem"
