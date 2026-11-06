"""Intégration mémoire MCP et clients des serveurs externes."""

from .client import (
    MCPExternalClient,
    get_mcp_client,
)
from .base.config import MCPClientConfig
from .base.rpc import (
    MCPClientError,
    MCPConnectionError,
    MCPTimeoutError,
)
from .memory import (
    MemoryManager,
    get_memory_manager,
    FREQUENT_ACCESS_THRESHOLD,
    EPISODIC_MEMORY_MAX_AGE_DAYS,
)

__all__ = [
    "MCPExternalClient",
    "MCPClientConfig",
    "MCPClientError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "get_mcp_client",
    "MemoryManager",
    "get_memory_manager",
    "FREQUENT_ACCESS_THRESHOLD",
    "EPISODIC_MEMORY_MAX_AGE_DAYS",
]
