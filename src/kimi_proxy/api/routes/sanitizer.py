"""
Routes API pour le sanitizer (Phase 1).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...features.sanitizer.storage import (
    get_masked_content,
    list_masked_contents,
    get_sanitizer_stats,
)
from ...config.loader import get_config

router = APIRouter()

# État global du sanitizer (idéalement dans une classe ou DB)
_sanitizer_enabled = True


@router.get("/mask/{content_hash}")
async def get_masked_content_endpoint(content_hash: str):
    """Récupère le contenu masqué par son hash."""
    content = get_masked_content(content_hash)
    if not content:
        return JSONResponse(
            status_code=404,
            content={"error": "Contenu masqué non trouvé", "hash": content_hash}
        )
    
    return {
        "hash": content["content_hash"],
        "preview": content["preview"],
        "tags": content["tags"].split(",") if content["tags"] else [],
        "token_count": content["token_count"],
        "created_at": content["created_at"],
        "file_path": content["file_path"],
        "original_content": content["original_content"]
    }


@router.get("/mask")
async def list_masked_content(limit: int = 50):
    """Liste les contenus masqués récents."""
    items = list_masked_contents(limit)
    
    return {
        "items": items,
        "total": len(items)
    }


@router.get("/sanitizer/stats")
async def get_sanitizer_stats_endpoint():
    """Retourne les statistiques du sanitizer."""
    config = get_sanitizer_config()
    stats = get_sanitizer_stats()
    
    return {
        "enabled": config.get("enabled", True),
        "threshold_tokens": config.get("threshold_tokens", 1000),
        "preview_length": config.get("preview_length", 200),
        "tmp_dir": config.get("tmp_dir", "/tmp/kimi_proxy_masked"),
        "stats": stats
    }


@router.post("/sanitizer/toggle")
async def toggle_sanitizer(request: Request):
    """Active/désactive le sanitizer."""
    global _sanitizer_enabled
    data = await request.json()
    enabled = data.get("enabled", True)
    
    _sanitizer_enabled = enabled
    
    return {
        "enabled": enabled,
        "message": f"Sanitizer {'activé' if enabled else 'désactivé'}"
    }


def get_sanitizer_config():
    """Récupère la configuration du sanitizer."""
    config = get_config()
    sanitizer_config = config.get("sanitizer", {})
    
    return {
        "enabled": sanitizer_config.get("enabled", True),
        "threshold_tokens": sanitizer_config.get("threshold_tokens", 1000),
        "preview_length": sanitizer_config.get("preview_length", 200),
        "tmp_dir": sanitizer_config.get("tmp_dir", "/tmp/kimi_proxy_masked"),
        "fallback_threshold": sanitizer_config.get("routing", {}).get("fallback_threshold", 0.90),
        "heavy_duty_fallback": sanitizer_config.get("routing", {}).get("heavy_duty_fallback", True),
    }


def is_sanitizer_enabled() -> bool:
    """Vérifie si le sanitizer est activé."""
    return _sanitizer_enabled
