"""
Routes API par domaine.
"""

from . import sessions
from . import providers
from . import proxy
from . import exports
from . import sanitizer
from . import mcp
from . import compression
from . import compaction
from . import health
from . import websocket
from . import models
from . import memory
from . import mcp_gateway
from . import mcp_passthrough

__all__ = [
    "sessions",
    "providers",
    "proxy",
    "exports",
    "sanitizer",
    "mcp",
    "compression",
    "compaction",
    "health",
    "websocket",
    "models",
    "memory",
    "mcp_gateway",
    "mcp_passthrough",
]
