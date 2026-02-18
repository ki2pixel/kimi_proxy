"""
Analyseur de mémoire MCP pour les messages.
"""
from typing import List, Dict, Any
from dataclasses import dataclass, field

from .detector import MCPDetector
from ...core.tokens import count_tokens_text
from ...core.constants import MCP_MIN_MEMORY_TOKENS


@dataclass
class MemoryAnalysisResult:
    """Résultat de l'analyse de mémoire."""
    memory_tokens: int = 0
    chat_tokens: int = 0
    total_tokens: int = 0
    memory_ratio: float = 0.0
    segments: List[Dict[str, Any]] = field(default_factory=list)
    has_memory: bool = False
    segment_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_tokens": self.memory_tokens,
            "chat_tokens": self.chat_tokens,
            "total_tokens": self.total_tokens,
            "memory_ratio": round(self.memory_ratio, 2),
            "segments": self.segments,
            "has_memory": self.has_memory,
            "segment_count": self.segment_count
        }


def calculate_memory_ratio(memory_tokens: int, total_tokens: int) -> float:
    """Calcule le ratio mémoire/total."""
    return (memory_tokens / total_tokens * 100) if total_tokens > 0 else 0


def analyze_mcp_memory_in_messages(
    messages: List[dict],
    min_tokens: int = MCP_MIN_MEMORY_TOKENS
) -> MemoryAnalysisResult:
    """
    Analyse une liste de messages pour détecter et compter les tokens mémoire MCP.
    
    Args:
        messages: Liste de messages au format OpenAI
        min_tokens: Seuil minimum pour considérer un segment comme mémoire
        
    Returns:
        MemoryAnalysisResult avec les métriques détaillées
    """
    total_tokens = 0
    memory_tokens = 0
    all_segments = []
    detector = MCPDetector(min_tokens=min_tokens)
    
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        
        if not isinstance(content, str):
            continue
        
        msg_tokens = count_tokens_text(content)
        total_tokens += msg_tokens
        
        # Extrait les segments mémoire
        segments = detector.detect(content)
        msg_memory_tokens = sum(s.tokens for s in segments)
        memory_tokens += msg_memory_tokens
        all_segments.extend([s.to_dict() for s in segments])
    
    chat_tokens = total_tokens - memory_tokens
    memory_ratio = calculate_memory_ratio(memory_tokens, total_tokens)
    
    return MemoryAnalysisResult(
        memory_tokens=memory_tokens,
        chat_tokens=chat_tokens,
        total_tokens=total_tokens,
        memory_ratio=round(memory_ratio, 2),
        segments=all_segments,
        has_memory=memory_tokens > 0,
        segment_count=len(all_segments)
    )
