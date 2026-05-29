"""
Router principal de l'API.
"""
from fastapi import APIRouter

from .routes import (
    sanitizer,
    mcp,
    compression,
    compaction,
    health,
    models,
    memory,
    proxy,
    mcp_gateway,
    mcp_passthrough,
)

# Router principal
api_router = APIRouter()

# Inclusion des sous-routers
api_router.include_router(sanitizer.router, prefix="/api", tags=["sanitizer"])
api_router.include_router(mcp.router, prefix="/api", tags=["mcp"])
api_router.include_router(compression.router, prefix="/api/compress", tags=["compression"])
api_router.include_router(compaction.router, prefix="/api/compaction", tags=["compaction"])
api_router.include_router(health.router, prefix="", tags=["health"])

# MCP Gateway (Observation Masking)
api_router.include_router(mcp_gateway.router, prefix="/api", tags=["mcp-gateway"])

# === API STANDARDS ===
# ✅ Routes standardisées sous /api
api_router.include_router(models.router, prefix="/api/models", tags=["models"])
api_router.include_router(models.openai_router, prefix="", tags=["models-openai"])
api_router.include_router(proxy.router, prefix="", tags=["proxy"])
api_router.include_router(mcp_passthrough.router, prefix="", tags=["mcp-passthrough"])