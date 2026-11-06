"""Routes API pour le health check."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check public minimal."""
    return {
        "status": "ok",
        "version": "2.0.0-mcp",
    }
