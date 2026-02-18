"""
MCP Phase 3 & 4 - Intégration mémoire avancée et nouveaux serveurs MCP.

Modules:
- detector: Détection des balises MCP
- analyzer: Analyse de mémoire dans les messages
- storage: Stockage des métriques mémoire
- client: Client pour serveurs MCP externes (Qdrant, Compression, Phase 4)
- memory: Gestion de mémoire standardisée (fréquente/épisodique)
"""

# Phase 2 - Base
from .detector import (
    MCPDetector, 
    extract_mcp_memory_content,
    # Phase 4
    extract_phase4_tools,
    get_detected_mcp_servers,
)
from .analyzer import (
    analyze_mcp_memory_in_messages,
    calculate_memory_ratio,
    MemoryAnalysisResult,
)
from .storage import (
    save_memory_metrics,
    get_session_memory_stats,
    get_memory_history,
    get_global_memory_stats,
)

# Phase 3 - Avancé
from .client import (
    MCPExternalClient,
    MCPClientConfig,
    MCPClientError,
    MCPConnectionError,
    MCPTimeoutError,
    get_mcp_client,
    reset_mcp_client,
)
from .memory import (
    MemoryManager,
    get_memory_manager,
    reset_memory_manager,
    FREQUENT_ACCESS_THRESHOLD,
    EPISODIC_MEMORY_MAX_AGE_DAYS,
)

# Phase 4 - Imports conditionnels pour éviter les imports circulaires
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.core.models import (
        TaskMasterTask,
        TaskMasterStats,
        SequentialThinkingStep,
        FileSystemResult,
        JsonQueryResult,
        MCPToolCall,
        MCPPhase4ServerStatus,
    )

__all__ = [
    # Phase 2
    "MCPDetector",
    "extract_mcp_memory_content",
    "analyze_mcp_memory_in_messages",
    "calculate_memory_ratio",
    "MemoryAnalysisResult",
    "save_memory_metrics",
    "get_session_memory_stats",
    "get_memory_history",
    "get_global_memory_stats",
    # Phase 3
    "MCPExternalClient",
    "MCPClientConfig",
    "MCPClientError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "get_mcp_client",
    "reset_mcp_client",
    "MemoryManager",
    "get_memory_manager",
    "reset_memory_manager",
    "FREQUENT_ACCESS_THRESHOLD",
    "EPISODIC_MEMORY_MAX_AGE_DAYS",
    # Phase 4
    "extract_phase4_tools",
    "get_detected_mcp_servers",
]
