"""Router principal de l'API."""
from fastapi import APIRouter, Depends
from .dependencies import verify_admin_key, verify_admin_key_x_header

from .routes import (
    sanitizer,
    mcp,
    health,
    models,
    mcp_gateway,
    mcp_passthrough,
)

api_router = APIRouter()

api_router.include_router(
    sanitizer.router,
    prefix="/api",
    tags=["sanitizer"],
    dependencies=[Depends(verify_admin_key)],
)
api_router.include_router(
    mcp.router,
    prefix="/api",
    tags=["mcp"],
    dependencies=[Depends(verify_admin_key)],
)

api_router.include_router(health.router, prefix="", tags=["health"])

api_router.include_router(
    mcp_gateway.router,
    prefix="/api",
    tags=["mcp-gateway"],
    dependencies=[Depends(verify_admin_key)],
)

api_router.include_router(
    models.router,
    prefix="/api/models",
    tags=["models"],
    dependencies=[Depends(verify_admin_key)],
)
api_router.include_router(
    models.openai_router,
    prefix="",
    tags=["models-openai"],
    dependencies=[Depends(verify_admin_key)],
)
api_router.include_router(
    mcp_passthrough.router,
    prefix="",
    tags=["mcp-passthrough"],
    dependencies=[Depends(verify_admin_key_x_header)],
)
