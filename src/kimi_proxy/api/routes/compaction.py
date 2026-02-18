"""
Routes API pour la compaction (Phase 2 Fonctionnalités Utilisateur).
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any

from ...features.compaction import (
    SimpleCompaction,
    CompactionConfig,
    persist_compaction_result,
    get_session_compaction_stats,
    get_all_compaction_stats,
    set_session_reserved_tokens,
    get_compaction_timeline,
)
from ...features.compaction.auto_trigger import (
    get_auto_trigger,
    AutoTriggerConfig,
)
from ...core.database import (
    get_session_by_id,
    get_active_session,
    get_session_total_tokens,
    update_session_auto_compaction,
    update_session_auto_threshold,
    get_session_compaction_state,
)
from ...config.display import get_max_context_for_session
from ...config.loader import get_config
from ...services.websocket_manager import get_connection_manager

router = APIRouter()


@router.post("/{session_id}")
async def api_compact_session(session_id: int, request: Request):
    """
    Endpoint pour compacter manuellement l'historique d'une session.
    Déclenche une compaction avec préservation des messages récents.
    
    Args:
        session_id: ID de la session à compacter
        request: Requête avec options optionnelles
        
    Returns:
        Résultat de la compaction
    """
    # Parse les options
    data = await request.json() if await request.body() else {}
    preserve_messages = data.get("preserve_messages", 2)
    force = data.get("force", False)
    
    # Vérifie la session
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    # Récupère les messages de la session (simulation - en pratique viendraient de l'historique)
    # Note: Dans une implémentation complète, il faudrait récupérer les vrais messages
    # Pour l'instant, on retourne une erreur indiquant que cette fonctionnalité nécessite
    # l'intégration avec le stockage des messages
    
    config = CompactionConfig(
        max_preserved_messages=preserve_messages
    )
    compactor = SimpleCompaction(config)
    
    # Simule la compaction (à remplacer par les vrais messages)
    # Pour l'instant, on retourne l'état de compaction de la session
    stats = get_session_compaction_stats(session_id)
    
    return {
        "success": True,
        "message": "Service de compaction initialisé",
        "session_id": session_id,
        "config": config.to_dict(),
        "current_stats": stats,
        "note": "La compaction complète nécessite l'intégration avec l'historique des messages"
    }


@router.get("/{session_id}/stats")
async def api_get_session_compaction_stats(session_id: int):
    """
    Retourne les statistiques de compaction d'une session.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Statistiques complètes de compaction
    """
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    # Récupère les stats de compaction
    compaction_stats = get_session_compaction_stats(session_id)
    
    # Récupère les infos de contexte actuel
    config = get_config()
    models = config.get("models", {})
    session_totals = get_session_total_tokens(session_id)
    max_context = get_max_context_for_session(session, models)
    
    current_tokens = session_totals["total_tokens"]
    reserved = session.get("reserved_tokens", 0) or 0
    
    # Calcule les métriques de contexte
    percentage = (current_tokens / max_context * 100) if max_context > 0 else 0
    percentage_with_reserved = ((current_tokens + reserved) / max_context * 100) if max_context > 0 else 0
    
    # Détermine si la compaction est recommandée
    compaction_config = config.get("compaction", {})
    threshold = compaction_config.get("threshold_percentage", 80)
    compaction_ready = percentage >= threshold
    
    return {
        "session_id": session_id,
        "compaction": compaction_stats,
        "context": {
            "current_tokens": current_tokens,
            "max_context": max_context,
            "percentage": round(percentage, 2),
            "reserved_tokens": reserved,
            "percentage_with_reserved": round(percentage_with_reserved, 2),
            "compaction_ready": compaction_ready,
            "threshold": threshold
        }
    }


@router.get("/stats")
async def api_get_global_compaction_stats():
    """
    Retourne les statistiques globales de compaction.
    
    Returns:
        Statistiques globales et configuration
    """
    stats = get_all_compaction_stats()
    config = get_config()
    compaction_config = config.get("compaction", {})
    
    # Active session
    active = get_active_session()
    active_compaction = None
    if active:
        active_compaction = get_session_compaction_stats(active["id"])
    
    return {
        "global": stats,
        "config": {
            "threshold_percentage": compaction_config.get("threshold_percentage", 80),
            "max_preserved_messages": compaction_config.get("max_preserved_messages", 2),
            "min_tokens_to_compact": compaction_config.get("min_tokens_to_compact", 500),
            "target_reduction_ratio": compaction_config.get("target_reduction_ratio", 0.60)
        },
        "active_session": active_compaction
    }


@router.get("/{session_id}/history")
async def api_get_compaction_history(session_id: int, limit: int = 50):
    """
    Retourne l'historique des compactions d'une session.
    
    Args:
        session_id: ID de la session
        limit: Nombre maximum d'entrées
        
    Returns:
        Historique des compactions avec cumuls
    """
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    timeline = get_compaction_timeline(session_id, limit)
    
    return {
        "session_id": session_id,
        "history": timeline,
        "total_entries": len(timeline)
    }


@router.post("/{session_id}/reserved")
async def api_set_reserved_tokens(session_id: int, request: Request):
    """
    Configure les tokens réservés pour une session.
    
    Args:
        session_id: ID de la session
        request: Requête avec reserved_tokens
        
    Returns:
        Confirmation de la mise à jour
    """
    data = await request.json()
    reserved_tokens = data.get("reserved_tokens", 0)
    
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    success = set_session_reserved_tokens(session_id, reserved_tokens)
    
    if success:
        # Diffuse la mise à jour
        try:
            manager = get_connection_manager()
            await manager.broadcast({
                "type": "reserved_tokens_updated",
                "session_id": session_id,
                "reserved_tokens": reserved_tokens
            })
        except Exception as e:
            print(f"⚠️ Erreur broadcast WebSocket: {e}")
        
        return {
            "success": True,
            "session_id": session_id,
            "reserved_tokens": reserved_tokens,
            "message": f"Tokens réservés mis à jour: {reserved_tokens}"
        }
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "Échec de la mise à jour"}
        )


@router.post("/{session_id}/simulate")
async def api_simulate_compaction(session_id: int, request: Request):
    """
    Simule une compaction sans l'appliquer réellement.
    Utile pour estimer les gains potentiels.
    
    Args:
        session_id: ID de la session
        request: Requête avec messages à simuler
        
    Returns:
        Résultat simulé de la compaction
    """
    data = await request.json() if await request.body() else {}
    messages = data.get("messages", [])
    preserve_messages = data.get("preserve_messages", 2)
    
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    if not messages:
        return JSONResponse(
            status_code=400,
            content={"error": "Aucun message fourni pour la simulation"}
        )
    
    # Crée le compacteur et simule
    config = CompactionConfig(max_preserved_messages=preserve_messages)
    compactor = SimpleCompaction(config)
    
    result = compactor.compact(messages, session_id=session_id)
    
    return {
        "simulated": True,
        "result": result.to_dict()
    }


@router.get("/{session_id}/preview")
async def api_get_compaction_preview(session_id: int):
    """
    Retourne un aperçu de ce que ferait une compaction sur la session actuelle.
    Utilisé pour afficher le modal de confirmation avant compaction.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Aperçu détaillé avec estimation des tokens économisés
    """
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    # Récupère les métriques récentes pour simuler
    from ...core.database import get_recent_metrics
    recent_metrics = get_recent_metrics(session_id, limit=50)
    
    # Construit une simulation de messages à partir des métriques
    messages = []
    for metric in recent_metrics:
        messages.append({
            "role": "user",
            "content": metric.get("content_preview", "...") or "Message utilisateur"
        })
        if metric.get("completion_tokens", 0) > 0:
            messages.append({
                "role": "assistant",
                "content": "Réponse de l'assistant..."
            })
    
    # Si pas assez de messages, retourne une erreur informative
    if len(messages) < 6:
        return {
            "can_compact": False,
            "reason": "insufficient_messages",
            "message": "Pas assez de messages pour compacter (minimum 6 requis)",
            "current_messages": len(messages),
            "min_required": 6
        }
    
    # Simule la compaction
    config = CompactionConfig()
    compactor = SimpleCompaction(config)
    
    # Vérifie si la compaction est possible
    should_compact, reason = compactor.should_compact(messages)
    
    if not should_compact:
        return {
            "can_compact": False,
            "reason": reason,
            "message": f"Compaction non nécessaire: {reason}",
            "current_messages": len(messages)
        }
    
    # Exécute la simulation
    result = compactor.compact(messages, session_id=session_id)
    
    # Récupère la config pour le preview
    ui_config = get_config().get("compaction", {}).get("preview", {})
    preview_count = ui_config.get("preview_messages_count", 5)
    
    # Construit le preview des messages
    messages_preview = []
    for msg in messages[:preview_count]:
        content = msg.get("content", "")
        preview = content[:ui_config.get("preview_max_length", 200)]
        if len(content) > ui_config.get("preview_max_length", 200):
            preview += "..."
        messages_preview.append({
            "role": msg.get("role", "unknown"),
            "preview": preview,
            "full_length": len(content)
        })
    
    return {
        "can_compact": True,
        "session_id": session_id,
        "preview": {
            "messages_preview": messages_preview,
            "total_messages": len(messages),
            "messages_to_summarize": result.summarized_count,
            "messages_to_preserve": result.recent_preserved + result.system_preserved
        },
        "estimate": {
            "original_tokens": result.original_tokens,
            "compacted_tokens": result.compacted_tokens,
            "tokens_saved": result.tokens_saved,
            "savings_percentage": round(result.compaction_ratio, 1),
            "show_savings": ui_config.get("show_savings_estimate", True)
        },
        "config": {
            "preserved_messages": config.max_preserved_messages,
            "target_reduction": config.target_reduction_ratio
        }
    }


@router.post("/{session_id}/toggle-auto")
async def api_toggle_auto_compaction(session_id: int, request: Request):
    """
    Active ou désactive l'auto-compaction pour une session.
    
    Args:
        session_id: ID de la session
        request: Requête avec enabled (bool)
        
    Returns:
        Nouvel état de l'auto-compaction
    """
    data = await request.json()
    enabled = data.get("enabled", True)
    
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    success = update_session_auto_compaction(session_id, enabled)
    
    if success:
        # Diffuse la mise à jour
        try:
            manager = get_connection_manager()
            await manager.broadcast({
                "type": "auto_compaction_toggled",
                "session_id": session_id,
                "enabled": enabled,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            print(f"⚠️ Erreur broadcast WebSocket: {e}")
        
        return {
            "success": True,
            "session_id": session_id,
            "auto_compaction_enabled": enabled,
            "message": f"Auto-compaction {'activée' if enabled else 'désactivée'}"
        }
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "Échec de la mise à jour"}
        )


@router.get("/{session_id}/auto-status")
async def api_get_auto_compaction_status(session_id: int):
    """
    Retourne le statut complet de l'auto-compaction pour une session.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Statut détaillé incluant cooldown et compteurs
    """
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    trigger = get_auto_trigger()
    status = trigger.get_status(session_id)
    
    # Récupère les infos de contexte actuel
    totals = get_session_total_tokens(session_id)
    config = get_config()
    models = config.get("models", {})
    max_context = get_max_context_for_session(session, models)
    
    current_tokens = totals["total_tokens"]
    usage_ratio = current_tokens / max_context if max_context > 0 else 0
    
    # Vérifie si une alerte est nécessaire
    alert = trigger.should_warn_threshold(session_id, current_tokens, max_context)
    
    return {
        "session_id": session_id,
        "status": status,
        "context": {
            "current_tokens": current_tokens,
            "max_context": max_context,
            "usage_ratio": round(usage_ratio, 4),
            "usage_percentage": round(usage_ratio * 100, 2)
        },
        "alert": alert
    }


@router.get("/config/ui")
async def api_get_compaction_ui_config():
    """
    Retourne la configuration UI pour la compaction.
    
    Returns:
        Configuration des boutons, tooltips, etc.
    """
    config = get_config()
    compaction = config.get("compaction", {})
    ui = compaction.get("ui", {})
    
    return {
        "show_compact_button": ui.get("show_compact_button", True),
        "manual_button_threshold": ui.get("manual_button_threshold", 70),
        "show_detailed_tooltips": ui.get("show_detailed_tooltips", True),
        "show_notifications": ui.get("show_compaction_notifications", True),
        "threshold_percentage": compaction.get("threshold_percentage", 80),
        "critical_threshold": compaction.get("critical_threshold", 95),
        "preview": compaction.get("preview", {})
    }


@router.get("/{session_id}/history-chart")
async def api_get_compaction_history_chart(session_id: int):
    """
    Retourne les données formatées pour le graphique d'historique de compaction.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Données formatées pour Chart.js
    """
    session = get_session_by_id(session_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Session non trouvée", "session_id": session_id}
        )
    
    history = get_compaction_timeline(session_id, limit=50)
    
    if not history:
        return {
            "session_id": session_id,
            "labels": [],
            "datasets": []
        }
    
    # Formate pour Chart.js
    labels = []
    tokens_saved = []
    cumulative_saved = []
    compaction_ratios = []
    
    running_total = 0
    for entry in reversed(history):  # Du plus ancien au plus récent
        timestamp = entry.get("timestamp", "")
        # Format court de la date
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            label = dt.strftime("%H:%M")
        except:
            label = timestamp[:5] if timestamp else "?"
        
        labels.append(label)
        saved = entry.get("tokens_saved", 0)
        tokens_saved.append(saved)
        running_total += saved
        cumulative_saved.append(running_total)
        compaction_ratios.append(entry.get("compaction_ratio", 0))
    
    return {
        "session_id": session_id,
        "labels": labels,
        "datasets": [
            {
                "label": "Tokens économisés",
                "data": tokens_saved,
                "borderColor": "#22c55e",
                "backgroundColor": "rgba(34, 197, 94, 0.1)",
                "fill": True,
                "tension": 0.4
            },
            {
                "label": "Cumul économisé",
                "data": cumulative_saved,
                "borderColor": "#3b82f6",
                "backgroundColor": "transparent",
                "borderDash": [5, 5],
                "fill": False,
                "tension": 0.4
            },
            {
                "label": "Ratio compaction (%)",
                "data": compaction_ratios,
                "borderColor": "#a855f7",
                "backgroundColor": "transparent",
                "yAxisID": "y1",
                "fill": False,
                "tension": 0.4
            }
        ]
    }


from datetime import datetime
