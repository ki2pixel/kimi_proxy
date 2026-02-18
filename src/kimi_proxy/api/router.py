"""
Router principal de l'API.
"""
from fastapi import APIRouter

from .routes import (
    sessions,
    providers,
    proxy,
    exports,
    sanitizer,
    mcp,
    compression,
    compaction,
    health,
    websocket,
    models,
)

# Router principal
api_router = APIRouter()

# Inclusion des sous-routers
api_router.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
api_router.include_router(providers.router, prefix="/api/providers", tags=["providers"])
# ... autres routes existantes ...
api_router.include_router(exports.router, prefix="/api/export", tags=["exports"])
api_router.include_router(sanitizer.router, prefix="/api", tags=["sanitizer"])
api_router.include_router(mcp.router, prefix="/api", tags=["mcp"])
api_router.include_router(compression.router, prefix="/api/compress", tags=["compression"])
api_router.include_router(compaction.router, prefix="/api/compaction", tags=["compaction"])
api_router.include_router(health.router, prefix="", tags=["health"])

# === API STANDARDS ===
# Sert /models
api_router.include_router(models.router, prefix="/models", tags=["models"])
# Sert /chat/completions
api_router.include_router(proxy.router, prefix="", tags=["proxy"])