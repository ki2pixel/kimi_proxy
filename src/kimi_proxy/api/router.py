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
    memory,
    cline,
    mcp_gateway,
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

# MCP Gateway (Observation Masking)
api_router.include_router(mcp_gateway.router, prefix="/api", tags=["mcp-gateway"])

# Cline (Solution 1 - ledger local)
api_router.include_router(cline.router, prefix="", tags=["cline"])

# === API STANDARDS ===
# ✅ Routes standardisées sous /api
api_router.include_router(models.router, prefix="/api/models", tags=["models"])
api_router.include_router(models.openai_router, prefix="", tags=["models-openai"])
api_router.include_router(proxy.router, prefix="", tags=["proxy"])