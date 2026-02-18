"""
Routing dynamique - Context Window Fallback (Phase 1).
"""
from typing import Optional, Tuple, Dict, Any

from ...core.constants import DEFAULT_MAX_CONTEXT, CONTEXT_FALLBACK_THRESHOLD, DEFAULT_PROVIDER
from ...core.database import get_db, get_session_by_id


def find_heavy_duty_model(
    provider_key: str,
    current_model: str,
    required_context: int,
    models: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    """
    Trouve un modèle "Heavy Duty" (plus grand contexte) dans le même provider.
    
    Args:
        provider_key: Clé du provider
        current_model: Modèle actuel
        required_context: Contexte minimum requis
        models: Dictionnaire des modèles disponibles
        
    Returns:
        Clé du modèle fallback ou None si aucun trouvé
    """
    current_model_data = models.get(current_model, {})
    current_context = current_model_data.get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    # Cherche les modèles du même provider avec plus de contexte
    candidates = []
    for model_key, model_data in models.items():
        if model_data.get("provider") == provider_key:
            model_context = model_data.get("max_context_size", DEFAULT_MAX_CONTEXT)
            if model_context > current_context and model_context >= required_context:
                candidates.append((model_key, model_context))
    
    if not candidates:
        return None
    
    # Trie par contexte croissant pour prendre le plus petit suffisant
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


async def route_dynamic_model(
    session: dict,
    prompt_tokens: int,
    models: Dict[str, Dict[str, Any]],
    broadcast_callback = None
) -> Tuple[dict, Optional[dict]]:
    """
    Route dynamiquement vers un modèle plus grand si nécessaire.
    
    Args:
        session: Session active
        prompt_tokens: Nombre de tokens dans le prompt
        models: Dictionnaire des modèles disponibles
        broadcast_callback: Fonction pour broadcaster les événements
        
    Returns:
        Tuple (session_mise_à_jour, notification)
    """
    if not session:
        return session, None
    
    from ...config.display import get_max_context_for_session, get_model_display_name
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    current_model = session.get("model")
    max_context = get_max_context_for_session(session, models, DEFAULT_MAX_CONTEXT)
    
    # Vérifie si on dépasse le seuil de fallback
    usage_ratio = prompt_tokens / max_context if max_context > 0 else 0
    
    if usage_ratio < CONTEXT_FALLBACK_THRESHOLD:
        return session, None
    
    # Cherche un modèle plus grand
    fallback_model = find_heavy_duty_model(provider_key, current_model, prompt_tokens, models)
    
    if not fallback_model:
        # Aucun modèle plus grand disponible
        notification = {
            "type": "context_warning",
            "level": "critical",
            "message": f"⚠️ Contexte critique ({usage_ratio*100:.1f}%) - Aucun modèle plus grand disponible",
            "current_model": current_model,
            "prompt_tokens": prompt_tokens,
            "max_context": max_context
        }
        return session, notification
    
    # Effectue le fallback
    old_model = current_model
    session["model"] = fallback_model
    new_max_context = models.get(fallback_model, {}).get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    # Met à jour en DB
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE sessions SET model = ? WHERE id = ?",
                (fallback_model, session["id"])
            )
            conn.commit()
        except Exception as e:
            print(f"⚠️ Erreur mise à jour modèle session: {e}")
    
    print(f"🔄 [ROUTING] Fallback: {old_model} → {fallback_model} "
          f"({max_context/1024:.0f}K → {new_max_context/1024:.0f}K contexte)")
    
    notification = {
        "type": "model_fallback",
        "level": "warning",
        "message": f"Basculement automatique vers {get_model_display_name(fallback_model)}",
        "old_model": old_model,
        "new_model": fallback_model,
        "old_context": max_context,
        "new_context": new_max_context,
        "prompt_tokens": prompt_tokens,
        "reason": f"Contexte dépassé ({usage_ratio*100:.1f}%)"
    }
    
    # Broadcast si callback fourni
    if broadcast_callback:
        await broadcast_callback({
            "type": "sanitizer_event",
            "event": notification,
            "session_id": session["id"]
        })
    
    return session, notification


def get_session_total_tokens(session_id: int) -> Dict[str, int]:
    """
    Calcule le total cumulé des tokens pour une session.
    
    Logique:
    - Input: Somme des prompt_tokens (réels) sinon estimated_tokens
    - Output: Somme des completion_tokens (réels)
    - Total: Input + Output
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                estimated_tokens,
                prompt_tokens,
                completion_tokens,
                is_estimated
            FROM metrics 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,))
        
        rows = cursor.fetchall()
    
    total_input = 0
    total_output = 0
    
    for row in rows:
        estimated = row[0] or 0
        prompt = row[1] or 0
        completion = row[2] or 0
        
        # Pour l'input: utilise prompt_tokens si disponible, sinon estimated_tokens
        if prompt > 0:
            total_input += prompt
        else:
            total_input += estimated
        
        # Pour l'output: toujours completion_tokens
        total_output += completion
    
    return {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output
    }
