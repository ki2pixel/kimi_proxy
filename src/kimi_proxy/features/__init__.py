"""
Fonctionnalités horizontales du Kimi Proxy Dashboard.
"""

from .log_watcher import LogWatcher, create_log_watcher
from .sanitizer import ContentMasker, sanitize_messages, get_masked_content, list_masked_contents
from .mcp import (
    MCPDetector,
    analyze_mcp_memory_in_messages,
    save_memory_metrics,
    get_session_memory_stats,
)
from .compression import (
    compress_session_history,
    compress_history_heuristic,
    get_compression_stats,
    summarize_with_llm,
)

__all__ = [
    # Log Watcher
    "LogWatcher",
    "create_log_watcher",
    # Sanitizer
    "ContentMasker",
    "sanitize_messages",
    "get_masked_content",
    "list_masked_contents",
    # MCP
    "MCPDetector",
    "analyze_mcp_memory_in_messages",
    "save_memory_metrics",
    "get_session_memory_stats",
    # Compression
    "compress_session_history",
    "compress_history_heuristic",
    "get_compression_stats",
    "summarize_with_llm",
]
