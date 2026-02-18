"""
Compression Phase 3 - Compression de dernier recours.
"""

from .heuristic import compress_history_heuristic, CompressionResult
from .summarizer import summarize_with_llm
from .storage import (
    compress_session_history,
    get_compression_stats,
    get_session_compression_logs,
)

__all__ = [
    "compress_history_heuristic",
    "CompressionResult",
    "summarize_with_llm",
    "compress_session_history",
    "get_compression_stats",
    "get_session_compression_logs",
]
