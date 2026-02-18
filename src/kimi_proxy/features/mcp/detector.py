"""
Détection des balises MCP et contenus mémoire.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from ...core.constants import MCP_PATTERNS, MCP_MIN_MEMORY_TOKENS
from ...core.tokens import count_tokens_text


@dataclass
class MemorySegment:
    """Segment de mémoire détecté."""
    type: str
    content: str
    tokens: int
    position: Tuple[int, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "tokens": self.tokens,
            "position": self.position
        }


class MCPDetector:
    """Détecteur de contenu MCP mémoire."""
    
    def __init__(self, min_tokens: int = MCP_MIN_MEMORY_TOKENS):
        self.min_tokens = min_tokens
        self.patterns = {
            'memory_tag': re.compile(MCP_PATTERNS['memory_tag'], re.DOTALL | re.IGNORECASE),
            'memory_ref': re.compile(MCP_PATTERNS['memory_ref'], re.IGNORECASE),
            'memory_block': re.compile(MCP_PATTERNS['memory_block'], re.DOTALL | re.IGNORECASE),
            'mcp_result': re.compile(MCP_PATTERNS['mcp_result'], re.DOTALL | re.IGNORECASE),
            'mcp_tool': re.compile(MCP_PATTERNS['mcp_tool'], re.DOTALL | re.IGNORECASE),
            'context_memory': re.compile(MCP_PATTERNS['context_memory'], re.IGNORECASE),
            'recall_tag': re.compile(MCP_PATTERNS['recall_tag'], re.IGNORECASE),
            'remember_tag': re.compile(MCP_PATTERNS['remember_tag'], re.IGNORECASE),
            'mcp_memory_bank': re.compile(MCP_PATTERNS['mcp_memory_bank'], re.IGNORECASE),
            'memory_header': re.compile(MCP_PATTERNS['memory_header'], re.IGNORECASE),
            'memory_write_header': re.compile(MCP_PATTERNS['memory_write_header'], re.IGNORECASE),
            # Phase 4 - Nouveaux serveurs MCP
            'mcp_task_master': re.compile(MCP_PATTERNS['mcp_task_master'], re.IGNORECASE),
            'mcp_sequential_thinking': re.compile(MCP_PATTERNS['mcp_sequential_thinking'], re.IGNORECASE),
            'mcp_fast_filesystem': re.compile(MCP_PATTERNS['mcp_fast_filesystem'], re.IGNORECASE),
            'mcp_json_query': re.compile(MCP_PATTERNS['mcp_json_query'], re.IGNORECASE),
        }
    
    def detect(self, content: str) -> List[MemorySegment]:
        """
        Détecte les segments mémoire dans un contenu.
        
        Args:
            content: Texte à analyser
            
        Returns:
            Liste des segments détectés
        """
        segments = []
        
        if not content or not isinstance(content, str):
            return segments
        
        for pattern_name, pattern in self.patterns.items():
            matches = pattern.finditer(content)
            for match in matches:
                segment_content = match.group(0)
                token_count = count_tokens_text(segment_content)
                
                if token_count >= self.min_tokens:
                    segments.append(MemorySegment(
                        type=pattern_name,
                        content=segment_content,
                        tokens=token_count,
                        position=(match.start(), match.end())
                    ))
        
        return segments
    
    def has_memory(self, content: str) -> bool:
        """Vérifie si le contenu contient de la mémoire MCP."""
        return len(self.detect(content)) > 0
    
    def count_memory_tokens(self, content: str) -> int:
        """Compte les tokens de mémoire dans le contenu."""
        segments = self.detect(content)
        return sum(s.tokens for s in segments)
    
    # ==============================================================================
    # Phase 4 - Détection des nouveaux serveurs MCP
    # ==============================================================================
    
    def detect_phase4_tools(self, content: str) -> List[MemorySegment]:
        """
        Détecte les outils MCP Phase 4 dans un contenu.
        
        Args:
            content: Texte à analyser
            
        Returns:
            Liste des segments d'outils Phase 4 détectés
        """
        segments = []
        
        if not content or not isinstance(content, str):
            return segments
        
        phase4_patterns = [
            ('mcp_task_master', 'task_master'),
            ('mcp_sequential_thinking', 'sequential_thinking'),
            ('mcp_fast_filesystem', 'fast_filesystem'),
            ('mcp_json_query', 'json_query'),
        ]
        
        for pattern_name, server_type in phase4_patterns:
            pattern = self.patterns.get(pattern_name)
            if pattern:
                matches = pattern.finditer(content)
                for match in matches:
                    segment_content = match.group(0)
                    token_count = count_tokens_text(segment_content)
                    
                    if token_count >= self.min_tokens:
                        segments.append(MemorySegment(
                            type=f"phase4_{server_type}",
                            content=segment_content,
                            tokens=token_count,
                            position=(match.start(), match.end())
                        ))
        
        return segments
    
    def has_phase4_tools(self, content: str) -> bool:
        """Vérifie si le contenu contient des outils MCP Phase 4."""
        return len(self.detect_phase4_tools(content)) > 0
    
    def get_detected_phase4_servers(self, content: str) -> List[str]:
        """
        Récupère la liste des serveurs Phase 4 détectés.
        
        Args:
            content: Texte à analyser
            
        Returns:
            Liste des types de serveurs détectés
        """
        servers = set()
        segments = self.detect_phase4_tools(content)
        
        for segment in segments:
            server_type = segment.type.replace('phase4_', '')
            servers.add(server_type)
        
        return list(servers)


def extract_mcp_memory_content(content: str, min_tokens: int = MCP_MIN_MEMORY_TOKENS) -> List[Dict[str, Any]]:
    """
    Extrait le contenu MCP mémoire d'un message.
    
    Args:
        content: Texte à analyser
        min_tokens: Seuil minimum de tokens
        
    Returns:
        Liste des segments mémoire détectés avec métadonnées
    """
    detector = MCPDetector(min_tokens=min_tokens)
    segments = detector.detect(content)
    return [s.to_dict() for s in segments]


def extract_phase4_tools(content: str, min_tokens: int = MCP_MIN_MEMORY_TOKENS) -> List[Dict[str, Any]]:
    """
    Extrait les outils MCP Phase 4 d'un message.
    
    Args:
        content: Texte à analyser
        min_tokens: Seuil minimum de tokens
        
    Returns:
        Liste des outils Phase 4 détectés avec métadonnées
    """
    detector = MCPDetector(min_tokens=min_tokens)
    segments = detector.detect_phase4_tools(content)
    return [s.to_dict() for s in segments]


def get_detected_mcp_servers(content: str, min_tokens: int = MCP_MIN_MEMORY_TOKENS) -> Dict[str, List[str]]:
    """
    Récupère tous les serveurs MCP détectés dans un message.
    
    Args:
        content: Texte à analyser
        min_tokens: Seuil minimum de tokens
        
    Returns:
        Dictionnaire avec les serveurs détectés par catégorie
    """
    detector = MCPDetector(min_tokens=min_tokens)
    
    return {
        "memory_bank": detector.has_memory(content),
        "phase4_servers": detector.get_detected_phase4_servers(content),
        "has_mcp_content": detector.has_memory(content) or detector.has_phase4_tools(content)
    }
