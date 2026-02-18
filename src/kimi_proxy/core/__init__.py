"""
Cœur métier du Kimi Proxy Dashboard.
Modules indépendants sans dépendances externes au package.
"""

from .exceptions import (
    KimiProxyError,
    ConfigurationError,
    ProviderError,
    DatabaseError,
    TokenizationError,
)
from .constants import (
    DEFAULT_MAX_CONTEXT,
    DATABASE_FILE,
    DEFAULT_PROVIDER,
    RATE_LIMITS,
    MAX_RPM,
    RATE_LIMIT_WARNING_THRESHOLD,
    RATE_LIMIT_CRITICAL_THRESHOLD,
    CONTEXT_FALLBACK_THRESHOLD,
    MCP_MIN_MEMORY_TOKENS,
)
from .tokens import ENCODING, count_tokens_tiktoken, count_tokens_text
from .models import (
    Session,
    Metric,
    Provider,
    Model,
    MaskedContent,
    MemoryMetrics,
    CompressionLog,
)

__all__ = [
    # Exceptions
    "KimiProxyError",
    "ConfigurationError",
    "ProviderError",
    "DatabaseError",
    "TokenizationError",
    # Constants
    "DEFAULT_MAX_CONTEXT",
    "DATABASE_FILE",
    "DEFAULT_PROVIDER",
    "RATE_LIMITS",
    "MAX_RPM",
    "RATE_LIMIT_WARNING_THRESHOLD",
    "RATE_LIMIT_CRITICAL_THRESHOLD",
    "CONTEXT_FALLBACK_THRESHOLD",
    "MCP_MIN_MEMORY_TOKENS",
    # Tokens
    "ENCODING",
    "count_tokens_tiktoken",
    "count_tokens_text",
    # Models
    "Session",
    "Metric",
    "Provider",
    "Model",
    "MaskedContent",
    "MemoryMetrics",
    "CompressionLog",
]
