"""
Routes API pour la compression (Phase 3).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...features.compression.storage import (
    compress_session_history,
    get_compression_stats,
    get_session_compression_logs,
)
from ...core.database import get_session_by_id, get_session_total_tokens
from ...config.display import get_max_context_for_session
from ...config.loader import get_config
from ...services.websocket_manager import get_connection_manager

router = APIRouter()


@router.post("/{session_id}")
async def api_compress_session(session_id: int, request: Request):
    """
    Endpoint pour compresser manuellement l'historique d'une session.
    Filet de sécurité ultime contre les crashes de contexte.
    """
    data = await request.json() if await request.body() else {}
    force = data.get("force", False)
    
    # Vérifie la session
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    # Récupère la config
    config = get_config()
    models = config.get("models", {})
    compression_config = config.get("sanitizer", {}).get("compression", {})
    threshold = compression_config.get("threshold_percentage", 85)
    
    # Vérifie le seuil de contexte (sauf si force=True)
    if not force:
        session_totals = get_session_total_tokens(session_id)
        max_context = get_max_context_for_session(session, models)
        current_percentage = (session_totals["total_tokens"] / max_context * 100) if max_context > 0 else 0
        
        if current_percentage < threshold:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Contexte trop faible pour compression ({current_percentage:.1f}% < {threshold}%)",
                    "current_percentage": round(current_percentage, 2),
                    "threshold": threshold,
                    "hint": "Utilisez force=true pour forcer la compression"
                }
            )
    
    # Exécute la compression
    try:
        result = await compress_session_history(session_id)
        
        if result.error:
            return JSONResponse(
                status_code=400,
                content=result.to_dict()
            )
        
        # Notifie via WebSocket
        manager = get_connection_manager()
        await manager.broadcast({
            "type": "compression_event",
            "session_id": session_id,
            "timestamp": __import__('datetime').datetime.now().isoformat(),
            "compression": {
                "compressed": result.compressed,
                "original_tokens": result.original_tokens,
                "compressed_tokens": result.compressed_tokens,
                "tokens_saved": result.tokens_saved,
                "compression_ratio": result.compression_ratio,
                "messages_before": result.messages_before,
                "messages_after": result.messages_after
            }
        })
        
        return result.to_dict()
        
    except Exception as e:
        print(f"❌ [COMPRESSION] Erreur: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Erreur lors de la compression: {str(e)}"}
        )


@router.get("/{session_id}/stats")
async def api_get_compression_stats(session_id: int):
    """Retourne les statistiques de compression d'une session."""
    stats = get_compression_stats(session_id)
    
    # Ajoute l'état actuel de la session
    session = get_session_by_id(session_id)
    config = get_config()
    models = config.get("models", {})
    compression_config = config.get("sanitizer", {}).get("compression", {})
    threshold = compression_config.get("threshold_percentage", 85)
    
    session_totals = get_session_total_tokens(session_id) if session else {"total_tokens": 0}
    max_context = get_max_context_for_session(session, models) if session else 262144
    current_percentage = (session_totals["total_tokens"] / max_context * 100) if max_context > 0 else 0
    
    return {
        "session_id": session_id,
        "compression_stats": stats,
        "current_context": {
            "total_tokens": session_totals["total_tokens"],
            "max_context": max_context,
            "percentage": round(current_percentage, 2),
            "can_compress": current_percentage >= threshold
        },
        "config": {
            "threshold_percentage": threshold,
            "preserve_recent_exchanges": compression_config.get("preserve_recent_exchanges", 5)
        }
    }


@router.get("/stats")
async def api_get_global_compression_stats():
    """Retourne les statistiques globales de compression."""
    stats = get_compression_stats()
    config = get_config()
    compression_config = config.get("sanitizer", {}).get("compression", {})
    
    return {
        "global": stats,
        "config": {
            "threshold_percentage": compression_config.get("threshold_percentage", 85),
            "preserve_recent_exchanges": compression_config.get("preserve_recent_exchanges", 5),
            "summary_max_tokens": compression_config.get("summary_max_tokens", 500)
        }
    }
