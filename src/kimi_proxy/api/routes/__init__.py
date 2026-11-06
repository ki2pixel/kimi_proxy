"""Routes API par domaine."""

from . import sanitizer
from . import mcp
from . import health
from . import models
from . import mcp_gateway
from . import mcp_passthrough

__all__ = [
    "sanitizer",
    "mcp",
    "health",
    "models",
    "mcp_gateway",
    "mcp_passthrough",
]
