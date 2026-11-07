"""Routes API pour le sanitizer (Phase 1), en lecture seule."""
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ...features.sanitizer.storage import (
    get_masked_content,
    list_masked_contents,
    get_sanitizer_stats,
)
from ...config.loader import get_config, get_sanitizer_config

router = APIRouter()


@router.get("/mask/{content_hash}")
async def get_masked_content_endpoint(content_hash: str):
    """Récupère le contenu masqué par son hash."""
    content = await get_masked_content(content_hash)
    if not content:
        return JSONResponse(
            status_code=404,
            content={"error": "Contenu masqué non trouvé", "hash": content_hash},
        )

    return {
        "hash": content["content_hash"],
        "preview": content["preview"],
        "tags": content["tags"].split(",") if content["tags"] else [],
        "token_count": content["token_count"],
        "created_at": content["created_at"],
        "file_path": content["file_path"],
        "original_content": content["original_content"],
    }


@router.get("/mask")
async def list_masked_content(limit: int = 50):
    """Liste les contenus masqués récents."""
    items = await list_masked_contents(limit)

    return {
        "items": items,
        "total": len(items),
    }


@router.get("/sanitizer/stats")
async def get_sanitizer_stats_endpoint():
    """Retourne les statistiques du sanitizer."""
    config = get_sanitizer_config(get_config())
    stats = await get_sanitizer_stats()

    return {
        "enabled": config.get("enabled", True),
        "threshold_tokens": config.get("threshold_tokens", 1000),
        "preview_length": config.get("preview_length", 200),
        "tmp_dir": config.get(
            "tmp_dir",
            os.path.join(os.path.expanduser("~"), ".kimi", "tmp", "kimi_proxy_masked"),
        ),
        "stats": stats,
    }
