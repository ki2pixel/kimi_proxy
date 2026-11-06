"""Constantes globales du middleware Kimi Proxy MCP."""
import os

# Configuration par défaut
DEFAULT_MAX_CONTEXT = 262144  # 256K tokens
DATABASE_FILE = "sessions.db"
DEFAULT_PROVIDER = "managed:kimi-code"

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

# Chemins du log watcher
DEFAULT_CONTINUE_LOG_PATH = "~/.continue/logs/core.log"
DEFAULT_KIMI_LOG_PATH = "/home/kidpixel/.kimi/logs/kimi.log"
DEFAULT_KIMI_SESSIONS_PATH = "/home/kidpixel/.kimi/sessions"
