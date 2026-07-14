"""
Router principal de l'API.
"""
from fastapi import APIRouter, Depends
from .dependencies import verify_admin_key

from .routes import (
    sanitizer,
    mcp,
    compression,
    compaction,
    health,
    models,
    proxy,
    mcp_gateway,
    mcp_passthrough,
)

# Router principal
api_router = APIRouter()

# Inclusion des sous-routers avec dépendance d'authentification admin
api_router.include_router(
    sanitizer.router,
    prefix="/api",
    tags=["sanitizer"],
    dependencies=[Depends(verify_admin_key)]
)
api_router.include_router(
    mcp.router,
    prefix="/api",
    tags=["mcp"],
    dependencies=[Depends(verify_admin_key)]
)
api_router.include_router(
    compression.router,
    prefix="/api/compress",
    tags=["compression"],
    dependencies=[Depends(verify_admin_key)]
)
api_router.include_router(
    compaction.router,
    prefix="/api/compaction",
    tags=["compaction"],
    dependencies=[Depends(verify_admin_key)]
)

# Health router (public, mais la route détaillée interne sera protégée individuellement)
api_router.include_router(health.router, prefix="", tags=["health"])

# MCP Gateway (Observation Masking)
api_router.include_router(
    mcp_gateway.router,
    prefix="/api",
    tags=["mcp-gateway"],
    dependencies=[Depends(verify_admin_key)]
)

# === API STANDARDS ===
api_router.include_router(
    models.router,
    prefix="/api/models",
    tags=["models"],
    dependencies=[Depends(verify_admin_key)]
)
api_router.include_router(
    models.openai_router,
    prefix="",
    tags=["models-openai"],
    dependencies=[Depends(verify_admin_key)]
)
api_router.include_router(
    proxy.router,
    prefix="",
    tags=["proxy"],
    dependencies=[Depends(verify_admin_key)]
)
api_router.include_router(
    mcp_passthrough.router,
    prefix="",
    tags=["mcp-passthrough"],
    dependencies=[Depends(verify_admin_key)]
)