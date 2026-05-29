"""
Routes API par domaine.
"""

from . import proxy
from . import sanitizer
from . import mcp
from . import compression
from . import compaction
from . import health

from . import models
from . import memory
from . import mcp_gateway
from . import mcp_passthrough

__all__ = [
    "proxy",
    "sanitizer",
    "mcp",
    "compression",
    "compaction",
    "health",

    "models",
    "memory",
    "mcp_gateway",
    "mcp_passthrough",
]
