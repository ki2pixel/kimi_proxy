"""
Algorithme heuristique de compression d'historique.
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from ...core.tokens import count_tokens_tiktoken
from ...core.constants import DEFAULT_COMPRESSION_CONFIG


@dataclass
class CompressionResult:
    """Résultat d'une compression."""
    compressed: bool
    session_id: int = 0
    log_id: Optional[int] = None
    original_tokens: int = 0
    compressed_tokens: int = 0
    tokens_saved: int = 0
    compression_ratio: float = 0.0
    messages_before: int = 0
    messages_after: int = 0
    system_preserved: int = 0
    recent_preserved: int = 0
    summary: Optional[str] = None
    error: Optional[str] = None
    reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "compressed": self.compressed,
            "session_id": self.session_id,
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "tokens_saved": self.tokens_saved,
            "compression_ratio": round(self.compression_ratio, 2),
            "messages_before": self.messages_before,
            "messages_after": self.messages_after,
            "system_preserved": self.system_preserved,
            "recent_preserved": self.recent_preserved,
        }
        if self.log_id:
            result["log_id"] = self.log_id
        if self.summary:
            result["summary"] = self.summary
        if self.error:
            result["error"] = self.error
        if self.reason:
            result["reason"] = self.reason
        return result


def compress_history_heuristic(
    messages: List[dict],
    preserve_recent: int = None
) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Algorithme heuristique de compression:
    1. Préserve tous les messages système
    2. Garde les N derniers échanges (user + assistant)
    3. Le reste sera résumé
    
    Args:
        messages: Liste complète des messages
        preserve_recent: Nombre d'échanges récents à préserver (défaut: config)
        
    Returns:
        Tuple (messages compressés, métadonnées)
    """
    if preserve_recent is None:
        preserve_recent = DEFAULT_COMPRESSION_CONFIG["preserve_recent_exchanges"]
    
    if not messages:
        return messages, {
            "compressed": False,
            "reason": "no_messages",
            "original_tokens": 0
        }
    
    original_tokens = count_tokens_tiktoken(messages)
    
    # Sépare les messages par type
    system_messages = [m for m in messages if m.get("role") == "system"]
    non_system_messages = [m for m in messages if m.get("role") != "system"]
    
    if len(non_system_messages) <= preserve_recent * 2:
        return messages, {
            "compressed": False,
            "reason": "insufficient_messages",
            "original_tokens": original_tokens
        }
    
    # Garde les N derniers échanges
    preserve_count = preserve_recent * 2
    recent_messages = non_system_messages[-preserve_count:]
    messages_to_summarize = non_system_messages[:-preserve_count]
    
    metadata = {
        "compressed": True,
        "original_count": len(messages),
        "original_tokens": original_tokens,
        "system_count": len(system_messages),
        "preserved_recent_count": len(recent_messages),
        "summarized_count": len(messages_to_summarize),
        "messages_to_summarize": messages_to_summarize
    }
    
    return system_messages + recent_messages, metadata
