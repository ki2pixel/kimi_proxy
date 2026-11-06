"""Constantes globales du middleware Kimi Proxy MCP."""
import os

# Configuration par défaut
DEFAULT_MAX_CONTEXT = 262144  # 256K tokens
DATABASE_FILE = "sessions.db"
DEFAULT_PROVIDER = "managed:kimi-code"

# MCP tool response chunking
MCP_MAX_RESPONSE_TOKENS = 50000
MCP_CHUNK_OVERLAP_TOKENS = 1000

# Rate limiting
MAX_RPM = 40
RATE_LIMIT_WARNING_THRESHOLD = 0.875
RATE_LIMIT_CRITICAL_THRESHOLD = 0.95

# Sanitizer
DEFAULT_SANITIZER_CONFIG = {
    "enabled": True,
    "threshold_tokens": 1000,
    "preview_length": 200,
    "tmp_dir": os.path.join(os.path.expanduser("~"), ".kimi", "tmp", "kimi_proxy_masked"),
    "tags": ["@file", "@codebase", "@tool", "@console", "@output"],
}

# Circuit breaker de la passerelle MCP
DEFAULT_MCP_CB_ENABLED = True
DEFAULT_MCP_CB_MAX_FAILURES = 5
DEFAULT_MCP_CB_SIM_THRESHOLD = 0.85

# Compression (Phase 3)
DEFAULT_COMPRESSION_CONFIG = {
    "enabled": True,
    "threshold_percentage": 85,
    "preserve_recent_exchanges": 5,
    "summary_max_tokens": 500,
}

# Seuils d'alertes
ALERT_THRESHOLDS = {
    "caution": 80,
    "warning": 90,
    "critical": 95,
}

# Chemins du log watcher
DEFAULT_CONTINUE_LOG_PATH = "~/.continue/logs/core.log"
DEFAULT_KIMI_LOG_PATH = "/home/kidpixel/.kimi/logs/kimi.log"
DEFAULT_KIMI_SESSIONS_PATH = "/home/kidpixel/.kimi/sessions"
