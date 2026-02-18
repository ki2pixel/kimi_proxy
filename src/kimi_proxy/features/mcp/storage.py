"""
Stockage des métriques mémoire MCP.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional

from ...core.database import get_db


def save_memory_metrics(
    session_id: int,
    memory_tokens: int,
    chat_tokens: int,
    memory_ratio: float
) -> int:
    """
    Sauvegarde les métriques mémoire pour une session.
    
    Args:
        session_id: ID de la session
        memory_tokens: Tokens de mémoire
        chat_tokens: Tokens de chat
        memory_ratio: Ratio mémoire/chat
        
    Returns:
        ID de la métrique créée
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO memory_metrics 
                (session_id, timestamp, memory_tokens, chat_tokens, memory_ratio)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, datetime.now().isoformat(), memory_tokens, chat_tokens, memory_ratio))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde mémoire metrics: {e}")
            return -1


def get_session_memory_stats(session_id: int) -> Dict[str, Any]:
    """
    Récupère les statistiques mémoire d'une session.
    
    Args:
        session_id: ID de la session
        
    Returns:
        Dictionnaire avec memory_tokens, chat_tokens, memory_ratio
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT memory_tokens, chat_tokens, memory_ratio 
            FROM memory_metrics 
            WHERE session_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (session_id,))
        
        row = cursor.fetchone()
        
        if row:
            return {
                'memory_tokens': row[0] or 0,
                'chat_tokens': row[1] or 0,
                'memory_ratio': row[2] or 0
            }
        
        return {'memory_tokens': 0, 'chat_tokens': 0, 'memory_ratio': 0}


def get_memory_history(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Récupère l'historique des métriques mémoire d'une session.
    
    Args:
        session_id: ID de la session
        limit: Nombre maximum d'entrées
        
    Returns:
        Liste des entrées d'historique
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, memory_tokens, chat_tokens, memory_ratio
            FROM memory_metrics
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        
        return [{
            'timestamp': row[0],
            'memory_tokens': row[1],
            'chat_tokens': row[2],
            'memory_ratio': row[3]
        } for row in rows]


def get_global_memory_stats() -> Dict[str, Any]:
    """
    Récupère les statistiques globales de mémoire MCP.
    
    Returns:
        Statistiques globales
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(memory_tokens) FROM memory_metrics")
        total_memory_tokens = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(chat_tokens) FROM memory_metrics")
        total_chat_tokens = cursor.fetchone()[0] or 0
        
        cursor.execute(
            "SELECT COUNT(DISTINCT session_id) FROM memory_metrics WHERE memory_tokens > 0"
        )
        sessions_with_memory = cursor.fetchone()[0] or 0
        
        cursor.execute(
            "SELECT AVG(memory_ratio) FROM memory_metrics WHERE memory_tokens > 0"
        )
        avg_ratio = cursor.fetchone()[0] or 0
        
        total_tokens = total_memory_tokens + total_chat_tokens
        global_ratio = (total_memory_tokens / total_tokens * 100) if total_tokens > 0 else 0
        
        return {
            "total_memory_tokens": total_memory_tokens,
            "total_chat_tokens": total_chat_tokens,
            "total_tokens": total_tokens,
            "global_memory_ratio": round(global_ratio, 2),
            "average_session_ratio": round(avg_ratio, 2),
            "sessions_with_memory": sessions_with_memory
        }
