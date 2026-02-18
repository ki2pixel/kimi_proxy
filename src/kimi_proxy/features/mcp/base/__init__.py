"""
MCP Base Module - Fonctionnalités de base pour les clients MCP.
"""

from .config import MCPClientConfig
from .rpc import MCPRPCClient, MCPClientError, MCPConnectionError, MCPTimeoutError

__all__ = [
    "MCPClientConfig",
    "MCPRPCClient",
    "MCPClientError",
    "MCPConnectionError",
    "MCPTimeoutError",
]
