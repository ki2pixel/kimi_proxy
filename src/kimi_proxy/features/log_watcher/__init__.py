"""
Log Watcher - Surveillance des logs Continue pour PyCharm.
"""

from .watcher import AnalyticsSource, ContinueLogSource, KimiGlobalLogSource, KimiSessionSource, LogWatcher, create_log_watcher
from .patterns import TOKEN_PATTERNS, COMPILE_CHAT_PATTERNS, API_ERROR_PATTERNS
from .parser import KimiGlobalLogParser, KimiSessionParser, LogParser, parse_token_metrics

__all__ = [
    "AnalyticsSource",
    "ContinueLogSource",
    "KimiGlobalLogSource",
    "KimiSessionSource",
    "LogWatcher",
    "create_log_watcher",
    "TOKEN_PATTERNS",
    "COMPILE_CHAT_PATTERNS",
    "API_ERROR_PATTERNS",
    "KimiGlobalLogParser",
    "KimiSessionParser",
    "LogParser",
    "parse_token_metrics",
]
