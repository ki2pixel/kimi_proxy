"""
Stockage et persistance pour les opérations de compaction.
"""
from typing import List, Dict, Any, Optional

from ...core.database import (
    save_compaction_history,
    get_compaction_history,
    get_global_compaction_stats,
    get_session_compaction_state,
    update_session_reserved_tokens,
)
from ...services.websocket_manager import get_connection_manager
from .simple_compaction import CompactionResult


async def persist_compaction_result(
    result: CompactionResult,
    trigger_reason: str = "manual"
) -> int:
    """
    Persiste le résultat d'une compaction en base de données.
    
    Args:
        result: Résultat de la compaction
        trigger_reason: Raison du déclenchement
        
    Returns:
        ID de l'entrée créée
    """
    if not result.compacted:
        return 0
    
    history_id = save_compaction_history(
        session_id=result.session_id,
        tokens_before=result.original_tokens,
        tokens_after=result.compacted_tokens,
        preserved_messages=result.recent_preserved,
        summarized_messages=result.summarized_count,
        trigger_reason=trigger_reason
    )
    
    # Diffuse l'événement via WebSocket
    await _broadcast_compaction_event(result, history_id)
    
    return history_id


async def _broadcast_compaction_event(
    result: CompactionResult,
    history_id: int
):
    """
    Diffuse un événement de compaction via WebSocket.
    
    Args:
        result: Résultat de la compaction
        history_id: ID de l'historique créé
    """
    try:
        manager = get_connection_manager()
        await manager.broadcast({
            "type": "compaction_event",
            "session_id": result.session_id,
            "timestamp": result.timestamp,
            "history_id": history_id,
            "compaction": {
                "compacted": result.compacted,
                "original_tokens": result.original_tokens,
                "compacted_tokens": result.compacted_tokens,
                "tokens_saved": result.tokens_saved,
                "compaction_ratio": result.compaction_ratio,
                "messages_before": result.messages_before,
                "messages_after": result.messages_after,
                "summarized_count": result.summarized_count
            }
        })
    except Exception as e:
        # Log l'erreur mais ne fait pas échouer l'opération
        print(f"⚠️ Erreur broadcast WebSocket compaction: {e}")


def get_session_compaction_stats(session_id: int) -> Dict[str, Any]:
    """
    Récupère les statistiques complètes de compaction d'une session.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Statistiques de compaction
    """
    return get_session_compaction_state(session_id)


def get_all_compaction_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques globales de compaction.
    
    Returns:
        Statistiques globales
    """
    return get_global_compaction_stats()


def set_session_reserved_tokens(session_id: int, reserved_tokens: int) -> bool:
    """
    Configure les tokens réservés pour une session.
    
    Args:
        session_id: ID de la session
        reserved_tokens: Nombre de tokens à réserver
        
    Returns:
        True si mis à jour avec succès
    """
    return update_session_reserved_tokens(session_id, reserved_tokens)


def get_compaction_timeline(
    session_id: int,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Récupère la timeline des compactions d'une session.
    
    Args:
        session_id: ID de la session
        limit: Nombre maximum d'entrées
        
    Returns:
        Liste chronologique des compactions
    """
    history = get_compaction_history(session_id, limit)
    
    # Calcule les cumuls
    cumulative_saved = 0
    for entry in reversed(history):  # Du plus ancien au plus récent
        cumulative_saved += entry.get("tokens_saved", 0)
        entry["cumulative_saved"] = cumulative_saved
    
    return history
