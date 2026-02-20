"""
Routes API pour la gestion des sessions.
"""
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request

from ...core.database import (
    create_session,
    get_active_session,
    get_all_sessions,
    get_session_stats,
)
from ...services.websocket_manager import get_connection_manager
from ...config.loader import get_config
from ...config.display import (
    get_provider_display_name,
    get_provider_icon,
    get_provider_color,
    get_max_context_for_session,
)
from ...features.mcp.storage import get_session_memory_stats

router = APIRouter()


@router.post("")
async def api_create_session(request: Request):
    """Crée une nouvelle session."""
    data = await request.json()
    name = data.get("name", f"Session {datetime.now().strftime('%H:%M:%S')}")
    provider = data.get("provider", "managed:kimi-code")
    model = data.get("model")
    
    session = create_session(name, provider, model)
    
    # Récupère la config pour les modèles
    config = get_config()
    models = config.get("models", {})
    
    # Ajoute max_context à la réponse
    max_context = get_max_context_for_session(session, models)
    session_with_context = dict(session)
    session_with_context["max_context"] = max_context
    
    # Broadcast via WebSocket
    manager = get_connection_manager()
    await manager.broadcast({
        "type": "new_session",
        "session": session_with_context
    })
    
    return session_with_context


@router.get("")
async def api_get_sessions():
    """Liste toutes les sessions."""
    return get_all_sessions()


@router.get("/active")
async def api_get_active_session():
    """Récupère la session active avec ses statistiques."""
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    config = get_config()
    providers = config.get("providers", {})
    models = config.get("models", {})
    
    stats = get_session_stats(session["id"])
    
    provider_key = session.get("provider", "managed:kimi-code")
    provider_info = providers.get(provider_key, {})
    max_context = get_max_context_for_session(session, models)
    
    # Récupère les stats mémoire MCP
    memory_stats = get_session_memory_stats(session["id"])
    
    # Ajoute max_context à la session pour le frontend
    session_with_context = dict(session)
    session_with_context["max_context"] = max_context
    
    return {
        "session": session_with_context,
        "provider": {
            "key": provider_key,
            "name": get_provider_display_name(provider_key),
            "info": provider_info,
            "color": get_provider_color(provider_key),
            "icon": get_provider_icon(provider_key)
        },
        "memory": memory_stats,
        **stats
    }


@router.get("/{session_id}/memory")
async def api_get_session_memory(session_id: int):
    """Retourne les statistiques mémoire d'une session."""
    from ...features.mcp.storage import get_memory_history
    
    memory_stats = get_session_memory_stats(session_id)
    history = get_memory_history(session_id)
    
    return {
        "session_id": session_id,
        "current": memory_stats,
        "history": history
    }


# ============================================================================
# AUTO SESSION - Gestion du mode auto-création de sessions
# ============================================================================

@router.get("/auto-status")
async def api_get_auto_session_status():
    """Récupère le statut de l'auto-session pour la session active."""
    from ...core.auto_session import get_auto_session_status
    
    session = get_active_session()
    if not session:
        return {"enabled": True, "session_id": None}
    
    enabled = get_auto_session_status(session["id"])
    return {"enabled": enabled, "session_id": session["id"]}


@router.post("/toggle-auto")
async def api_toggle_auto_session(request: Request):
    """Active ou désactive l'auto-session pour la session active."""
    from ...core.auto_session import set_auto_session_status, get_auto_session_status
    
    data = await request.json()
    enabled = data.get("enabled", True)
    
    session = get_active_session()
    if not session:
        return {"error": "Aucune session active"}
    
    set_auto_session_status(session["id"], enabled)
    
    # Broadcast via WebSocket
    manager = get_connection_manager()
    await manager.broadcast({
        "type": "auto_session_toggled",
        "session_id": session["id"],
        "enabled": enabled
    })
    
    return {
        "enabled": get_auto_session_status(session["id"]),
        "session_id": session["id"]
    }
