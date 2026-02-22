"""
Routes API pour la gestion des sessions.
"""
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...core.database import (
    create_session,
    get_active_session,
    get_all_sessions,
    get_session_stats,
    set_active_session,
    delete_session,
    delete_sessions_bulk,
    vacuum_database,
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


# ============================================================================
# AUTO SESSION - Gestion du mode auto-création de sessions
# ============================================================================

@router.get("/auto-status")
async def api_get_auto_session_status():
    """Récupère le statut de l'auto-session pour la session active."""
    from fastapi.responses import JSONResponse
    
    # Retourner une valeur par défaut pour éviter les erreurs lors de l'initialisation
    # L'auto-session fonctionne indépendamment de cette route
    session = get_active_session()
    if not session:
        return JSONResponse({"enabled": True, "session_id": None})
    
    try:
        from ...core.auto_session import get_auto_session_status
        enabled = get_auto_session_status(session["id"])
        return JSONResponse({"enabled": enabled, "session_id": session["id"]})
    except Exception as e:
        # En cas d'erreur, retourner une valeur par défaut sécurisée
        print(f"⚠️ Erreur récupération statut auto-session: {e}")
        return JSONResponse({"enabled": True, "session_id": None})


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


@router.get("/{session_id}")
async def api_get_session(session_id: int):
    """Récupère une session spécifique avec ses statistiques."""
    session = get_active_session()
    if session and session["id"] == session_id:
        # Pour la session active, retourne les données complètes
        config = get_config()
        providers = config.get("providers", {})
        models = config.get("models", {})
        
        stats = get_session_stats(session_id)
        
        provider_key = session.get("provider", "managed:kimi-code")
        provider_info = providers.get(provider_key, {})
        max_context = get_max_context_for_session(session, models)
        
        # Récupère les stats mémoire MCP
        memory_stats = get_session_memory_stats(session_id)
        
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
    
    # Pour les sessions inactives, retourne juste les données de base
    session_data = get_session_by_id(session_id)
    if not session_data:
        return {"error": f"Session {session_id} introuvable"}
    
    config = get_config()
    models = config.get("models", {})
    max_context = get_max_context_for_session(session_data, models)
    
    session_with_context = dict(session_data)
    session_with_context["max_context"] = max_context
    
    return {
        "session": session_with_context,
        "provider": {
            "key": session_data.get("provider", "managed:kimi-code"),
            "name": get_provider_display_name(session_data.get("provider", "managed:kimi-code")),
            "color": get_provider_color(session_data.get("provider", "managed:kimi-code")),
            "icon": get_provider_icon(session_data.get("provider", "managed:kimi-code"))
        },
        "memory": get_session_memory_stats(session_id),
        **get_session_stats(session_id)
    }


@router.post("/{session_id}/activate")
async def api_activate_session(session_id: int):
    """Active une session spécifique."""
    session = get_active_session()
    if session and session["id"] == session_id:
        return {"message": "Session déjà active", "session_id": session_id}
    
    # Désactive la session actuelle si elle existe
    if session:
        # Note: La fonction set_active_session gère la logique de désactivation
        pass
    
    # Active la nouvelle session
    success = set_active_session(session_id)
    if not success:
        return {"error": "Session non trouvée", "session_id": session_id}
    
    # Récupère la session activée
    new_active = get_active_session()
    
    # Broadcast via WebSocket
    manager = get_connection_manager()
    await manager.broadcast({
        "type": "session_activated",
        "session_id": session_id,
        "session": new_active
    })
    
    return {
        "message": "Session activée",
        "session_id": session_id,
        "session": new_active
    }


# ============================================================================
# AUTO SESSION - Gestion du mode auto-création de sessions
# ============================================================================

@router.get("/auto-status")
async def api_get_auto_session_status():
    """Récupère le statut de l'auto-session pour la session active."""
    from fastapi.responses import JSONResponse
    
    # Retourner une valeur par défaut pour éviter les erreurs lors de l'initialisation
    # L'auto-session fonctionne indépendamment de cette route
    session = get_active_session()
    if not session:
        return JSONResponse({"enabled": True, "session_id": None})
    
    try:
        from ...core.auto_session import get_auto_session_status
        enabled = get_auto_session_status(session["id"])
        return JSONResponse({"enabled": enabled, "session_id": session["id"]})
    except Exception as e:
        # En cas d'erreur, retourner une valeur par défaut sécurisée
        print(f"⚠️ Erreur récupération statut auto-session: {e}")
        return JSONResponse({"enabled": True, "session_id": None})


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


@router.delete("")
async def api_delete_sessions_bulk(request: Request):
    """Supprime plusieurs sessions en bulk."""
    data = await request.json()
    session_ids = data.get("session_ids", [])
    
    if not session_ids:
        return {"error": "Aucun ID de session fourni"}
    
    # Vérifie qu'aucune session active n'est dans la liste
    active_session = get_active_session()
    if active_session and active_session["id"] in session_ids:
        return {"error": "Impossible de supprimer une session active"}
    
    # Supprime les sessions en bulk
    result = delete_sessions_bulk(session_ids)
    
    if not result["success"]:
        return {"error": f"Échec suppression sessions: {result['failed_ids']}"}
    
    # Exécute VACUUM automatiquement après suppression en bulk
    vacuum_result = vacuum_database()
    print(f"🧹 VACUUM automatique après suppression en bulk: {vacuum_result.get('message', 'Erreur')}")
    
    # Broadcast via WebSocket
    manager = get_connection_manager()
    await manager.broadcast({
        "type": "sessions_bulk_deleted",
        "session_ids": session_ids,
        "deleted_count": result["deleted_count"]
    })
    
    return result


@router.post("/vacuum")
async def api_vacuum_database():
    """Exécute VACUUM sur la base de données pour récupérer l'espace disque après suppressions."""
    import os
    import sqlite3
    from ...core.constants import DATABASE_FILE
    
    try:
        # Vérifie que le fichier existe
        if not os.path.exists(DATABASE_FILE):
            return {"error": "Base de données introuvable"}
        
        # Récupère la taille avant VACUUM
        size_before = os.path.getsize(DATABASE_FILE)
        
        # Exécute VACUUM
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Démarre une transaction pour VACUUM
        cursor.execute("VACUUM")
        conn.commit()
        conn.close()
        
        # Récupère la taille après VACUUM
        size_after = os.path.getsize(DATABASE_FILE)
        space_saved = size_before - size_after
        space_saved_mb = space_saved / (1024 * 1024)
        
        return {
            "message": "VACUUM exécuté avec succès",
            "database": {
                "path": DATABASE_FILE,
                "size_before_bytes": size_before,
                "size_after_bytes": size_after,
                "space_saved_bytes": space_saved,
                "space_saved_mb": round(space_saved_mb, 2)
            }
        }
        
    except Exception as e:
        return {"error": f"Erreur lors du VACUUM: {str(e)}"}


@router.get("/diagnostic")
async def api_get_sessions_diagnostic():
    """Fournit des informations de diagnostic sur les sessions et la base de données."""
    import os
    from ...core.database import get_all_sessions
    from ...core.constants import DATABASE_FILE
    
    try:
        # Informations sur les sessions
        sessions = get_all_sessions()
        session_count = len(sessions)
        
        # Informations sur la base de données
        db_size = os.path.getsize(DATABASE_FILE) if os.path.exists(DATABASE_FILE) else 0
        db_size_mb = db_size / (1024 * 1024)
        
        # Sessions par provider
        provider_stats = {}
        for session in sessions:
            provider = session.get("provider", "unknown")
            provider_stats[provider] = provider_stats.get(provider, 0) + 1
        
        # Sessions actives
        active_sessions = [s for s in sessions if s.get("is_active")]
        
        return {
            "database": {
                "file_size_bytes": db_size,
                "file_size_mb": round(db_size_mb, 2),
                "path": DATABASE_FILE
            },
            "sessions": {
                "total_count": session_count,
                "active_count": len(active_sessions),
                "inactive_count": session_count - len(active_sessions),
                "by_provider": provider_stats
            },
            "note": "Pour récupérer l'espace disque après suppressions, exécutez: VACUUM sur la base de données"
        }
        
    except Exception as e:
        return {"error": f"Erreur diagnostic: {str(e)}"}
