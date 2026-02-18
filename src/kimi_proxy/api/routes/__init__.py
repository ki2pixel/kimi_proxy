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
from . import health
from . import websocket
from . import models

__all__ = [
    "sessions",
    "providers",
    "proxy",
    "exports",
    "sanitizer",
    "mcp",
    "compression",
    "health",
    "websocket",
    "models",
]
