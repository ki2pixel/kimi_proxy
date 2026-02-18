"""
Stockage des logs de compression.
"""
from datetime import datetime
from typing import Dict, Any, Optional, List

from ...core.database import get_db, get_session_by_id, get_session_total_tokens
from ...core.tokens import count_tokens_tiktoken
from ...config.display import get_max_context_for_session
from .heuristic import compress_history_heuristic, CompressionResult
from .summarizer import summarize_with_llm


async def compress_session_history(
    session_id: int,
    config: dict = None,
    models: dict = None,
    force: bool = False
) -> CompressionResult:
    """
    Compression complète de l'historique d'une session.
    
    Args:
        session_id: ID de la session
        config: Configuration (optionnel)
        models: Dictionnaire des modèles (optionnel)
        force: Force la compression même si < seuil
        
    Returns:
        Résultat de la compression
    """
    session = get_session_by_id(session_id)
    if not session:
        return CompressionResult(
            compressed=False,
            session_id=session_id,
            error="Session non trouvée"
        )
    
    # Récupère les métriques de la session pour reconstruire l'historique
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT content_preview, prompt_tokens, completion_tokens, timestamp
            FROM metrics 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
        
        rows = cursor.fetchall()
    
    if not rows:
        return CompressionResult(
            compressed=False,
            session_id=session_id,
            error="Aucune métrique trouvée pour cette session"
        )
    
    # Reconstruit les messages à partir des métriques
    messages = []
    for row in rows:
        preview = row[0] or ""
        if preview:
            messages.append({"role": "user", "content": preview})
    
    # Applique l'heuristique de compression
    compressed_messages, metadata = compress_history_heuristic(messages)
    
    if not metadata.get("compressed"):
        return CompressionResult(
            compressed=False,
            session_id=session_id,
            reason=metadata.get("reason"),
            original_tokens=metadata.get("original_tokens", 0)
        )
    
    # Génère le résumé pour les messages du milieu
    messages_to_summarize = metadata.get("messages_to_summarize", [])
    summary = None
    
    if messages_to_summarize:
        summary = await summarize_with_llm(messages_to_summarize, session)
        
        # Insère le résumé comme message assistant
        summary_message = {
            "role": "assistant",
            "content": f"[📋 RÉSUMÉ DE L'HISTORIQUE PRÉCÉDENT]\n\n{summary}\n\n[Fin du résumé - Conversation continue]"
        }
        
        # Structure finale: système + résumé + récents
        final_messages = []
        
        # Ajoute les messages système
        system_count = metadata.get("system_count", 0)
        if system_count > 0:
            final_messages.extend(compressed_messages[:system_count])
        
        # Ajoute le résumé
        final_messages.append(summary_message)
        
        # Ajoute les messages récents
        preserved_count = metadata.get("preserved_recent_count", 0)
        if preserved_count > 0:
            final_messages.extend(compressed_messages[-preserved_count:])
    else:
        final_messages = compressed_messages
    
    # Calcule les statistiques
    compressed_tokens = count_tokens_tiktoken(final_messages)
    original_tokens = metadata.get("original_tokens", 0)
    tokens_saved = original_tokens - compressed_tokens
    compression_ratio = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0
    
    # Sauvegarde dans le log de compression
    summary_preview = ""
    if len(final_messages) > metadata.get("system_count", 0):
        summary_preview = final_messages[metadata.get("system_count", 0)].get("content", "")[:200]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO compression_log 
                (session_id, timestamp, original_tokens, compressed_tokens, compression_ratio, summary_preview)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, datetime.now().isoformat(), original_tokens, compressed_tokens,
                  compression_ratio, summary_preview))
            conn.commit()
            log_id = cursor.lastrowid
        except Exception as e:
            print(f"⚠️ [COMPRESSION] Erreur sauvegarde log: {e}")
            log_id = None
    
    print(f"🗜️ [COMPRESSION] Session {session_id}: {original_tokens} → {compressed_tokens} tokens "
          f"({compression_ratio:.1f}% économisés)")
    
    return CompressionResult(
        compressed=True,
        session_id=session_id,
        log_id=log_id,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        tokens_saved=tokens_saved,
        compression_ratio=round(compression_ratio, 2),
        messages_before=metadata.get("original_count", 0),
        messages_after=len(final_messages),
        system_preserved=metadata.get("system_count", 0),
        recent_preserved=metadata.get("preserved_recent_count", 0),
        summary=summary
    )


def get_compression_stats(session_id: int = None) -> Dict[str, Any]:
    """
    Récupère les statistiques de compression.
    
    Args:
        session_id: ID de la session (optionnel, si None = global)
        
    Returns:
        Statistiques de compression
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        if session_id:
            cursor.execute("""
                SELECT COUNT(*), SUM(original_tokens), SUM(compressed_tokens), AVG(compression_ratio)
                FROM compression_log 
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return {
                "total_compressions": row[0] or 0,
                "total_original_tokens": row[1] or 0,
                "total_compressed_tokens": row[2] or 0,
                "avg_compression_ratio": round(row[3] or 0, 2)
            }
        else:
            cursor.execute("""
                SELECT COUNT(*), SUM(original_tokens), SUM(compressed_tokens), AVG(compression_ratio)
                FROM compression_log
            """)
            row = cursor.fetchone()
            return {
                "total_compressions": row[0] or 0,
                "total_original_tokens": row[1] or 0,
                "total_compressed_tokens": row[2] or 0,
                "avg_compression_ratio": round(row[3] or 0, 2)
            }


def get_session_compression_logs(session_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Récupère les logs de compression d'une session.
    
    Args:
        session_id: ID de la session
        limit: Nombre maximum de logs
        
    Returns:
        Liste des logs
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, original_tokens, compressed_tokens, 
                   compression_ratio, summary_preview
            FROM compression_log
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        
        return [{
            "id": row[0],
            "timestamp": row[1],
            "original_tokens": row[2],
            "compressed_tokens": row[3],
            "compression_ratio": row[4],
            "summary_preview": row[5]
        } for row in rows]
