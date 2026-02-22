"""
Configuration MCP centralisée.

Fournit MCPClientConfig pour tous les serveurs MCP.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class MCPClientConfig:
    """Configuration pour tous les serveurs MCP."""
    
    # Qdrant MCP
    qdrant_url: Optional[str] = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "kimi_proxy_memory"
    search_timeout_ms: float = 50.0  # <50ms pour recherche
    
    # Context Compression MCP
    compression_url: Optional[str] = "http://localhost:8001"
    compression_api_key: Optional[str] = None
    compression_timeout_ms: float = 5000.0
    
    # Shrimp Task Manager MCP (Phase 4)
    task_master_url: Optional[str] = "http://localhost:8002"
    task_master_api_key: Optional[str] = None
    task_master_timeout_ms: float = 30000.0  # 30s
    
    # Sequential Thinking MCP (Phase 4)
    sequential_thinking_url: Optional[str] = "http://localhost:8003"
    sequential_thinking_api_key: Optional[str] = None
    sequential_thinking_timeout_ms: float = 60000.0  # 60s
    
    # Fast Filesystem MCP (Phase 4)
    fast_filesystem_url: Optional[str] = "http://localhost:8004"
    fast_filesystem_api_key: Optional[str] = None
    fast_filesystem_timeout_ms: float = 10000.0  # 10s
    
    # JSON Query MCP (Phase 4)
    json_query_url: Optional[str] = "http://localhost:8005"
    json_query_api_key: Optional[str] = None
    json_query_timeout_ms: float = 5000.0  # 5s
    
    # Configuration retry
    max_retries: int = 3
    retry_delay_ms: float = 100.0
    
    # Configuration cache
    enable_cache: bool = True
    cache_ttl_seconds: int = 300
    
    @classmethod
    def from_toml(cls, toml_config: Dict[str, Any]) -> "MCPClientConfig":
        """
        Charge la configuration depuis config.toml.
        
        Args:
            toml_config: Configuration chargée depuis config.toml
            
        Returns:
            Instance MCPClientConfig
        """
        mcp = toml_config.get("mcp", {})
        
        return cls(
            # Qdrant
            qdrant_url=mcp.get("qdrant", {}).get("url", "http://localhost:6333"),
            qdrant_api_key=mcp.get("qdrant", {}).get("api_key"),
            qdrant_collection=mcp.get("qdrant", {}).get("collection", "kimi_proxy_memory"),
            search_timeout_ms=mcp.get("qdrant", {}).get("search_timeout_ms", 50.0),
            
            # Compression
            compression_url=mcp.get("compression", {}).get("url", "http://localhost:8001"),
            compression_api_key=mcp.get("compression", {}).get("api_key"),
            compression_timeout_ms=mcp.get("compression", {}).get("compression_timeout_ms", 5000.0),
            
            # Shrimp Task Manager
            task_master_url=mcp.get("task_master", {}).get("url", "http://localhost:8002"),
            task_master_api_key=mcp.get("task_master", {}).get("api_key"),
            task_master_timeout_ms=mcp.get("task_master", {}).get("timeout_ms", 30000.0),
            
            # Sequential Thinking
            sequential_thinking_url=mcp.get("sequential_thinking", {}).get("url", "http://localhost:8003"),
            sequential_thinking_api_key=mcp.get("sequential_thinking", {}).get("api_key"),
            sequential_thinking_timeout_ms=mcp.get("sequential_thinking", {}).get("timeout_ms", 60000.0),
            
            # Fast Filesystem
            fast_filesystem_url=mcp.get("fast_filesystem", {}).get("url", "http://localhost:8004"),
            fast_filesystem_api_key=mcp.get("fast_filesystem", {}).get("api_key"),
            fast_filesystem_timeout_ms=mcp.get("fast_filesystem", {}).get("timeout_ms", 10000.0),
            
            # JSON Query
            json_query_url=mcp.get("json_query", {}).get("url", "http://localhost:8005"),
            json_query_api_key=mcp.get("json_query", {}).get("api_key"),
            json_query_timeout_ms=mcp.get("json_query", {}).get("timeout_ms", 5000.0),
            
            # Retry
            max_retries=mcp.get("retry", {}).get("max_retries", 3),
            retry_delay_ms=mcp.get("retry", {}).get("retry_delay_ms", 100.0),
            
            # Cache
            enable_cache=mcp.get("cache", {}).get("enable_cache", True),
            cache_ttl_seconds=mcp.get("cache", {}).get("cache_ttl_seconds", 300),
        )
