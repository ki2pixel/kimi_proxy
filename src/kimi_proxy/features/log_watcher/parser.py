"""
Parser pour extraire les métriques de tokens des logs.
"""
import re
from typing import Optional, Dict, Any, List

from .patterns import (
    TOKEN_PATTERNS, COMPILE_CHAT_PATTERNS, API_ERROR_PATTERNS,
    COMPILE_CHAT_START, COMPILE_CHAT_END, is_relevant_line
)
from ...core.models import TokenMetrics


class LogParser:
    """Parse les lignes de log pour extraire les métriques de tokens."""
    
    def __init__(self):
        self._compile_chat_buffer: List[str] = []
        self._in_compile_chat_block = False
    
    def parse_line(self, line: str) -> Optional[TokenMetrics]:
        """
        Parse une ligne de log et retourne les métriques si trouvées.
        
        Args:
            line: Ligne de log à parser
            
        Returns:
            TokenMetrics si des métriques sont trouvées, None sinon
        """
        # Détection du bloc CompileChat multi-lignes
        if COMPILE_CHAT_START.search(line):
            self._in_compile_chat_block = True
            self._compile_chat_buffer = [line]
            return None
        
        if self._in_compile_chat_block:
            self._compile_chat_buffer.append(line)
            
            # Fin du bloc si ligne vide ou nouvelle section
            if line.strip() == '' or (not line.startswith('-') and not line.startswith(' ')):
                self._in_compile_chat_block = False
                return self._parse_compile_chat_block()
            
            # Continue d'accumuler
            if len(self._compile_chat_buffer) < 10:  # Limite de sécurité
                return None
            else:
                self._in_compile_chat_block = False
                return self._parse_compile_chat_block()
        
        if not is_relevant_line(line):
            return None
        
        return self._extract_standard_metrics(line)
    
    def _extract_standard_metrics(self, line: str) -> Optional[TokenMetrics]:
        """
        Extrait les métriques standard d'une ligne de log avec support multi-formats.
        
        Supporte les formats OpenAI, Continue, Gemini, et JSON-like.
        Gère les estimations avec tilde (~) et les erreurs API.
        """
        metrics = TokenMetrics(
            source="logs",
            raw_line=line[:200],
            is_compile_chat=False,
            is_api_error=False
        )
        
        found = False
        
        # Extraction des patterns standards
        for pattern in TOKEN_PATTERNS:
            matches = pattern.findall(line)
            for match in matches:
                try:
                    value = int(match)
                    pattern_str = pattern.pattern.lower()
                    
                    if 'prompt' in pattern_str:
                        metrics.prompt_tokens = value
                        found = True
                    elif 'completion' in pattern_str:
                        metrics.completion_tokens = value
                        found = True
                    elif 'context' in pattern_str:
                        metrics.context_length = value
                        found = True
                    elif 'total' in pattern_str or pattern_str.startswith(r'"total_tokens"'):
                        metrics.total_tokens = value
                        found = True
                    else:
                        if metrics.total_tokens == 0:
                            metrics.total_tokens = value
                            found = True
                except (ValueError, IndexError):
                    continue
        
        # Extraction des erreurs API
        for pattern in API_ERROR_PATTERNS:
            match = pattern.search(line)
            if match:
                try:
                    value = int(match.group(1))
                    metrics.total_tokens = value
                    metrics.is_api_error = True
                    found = True
                except (ValueError, IndexError):
                    continue
        
        # Extraction des patterns CompileChat individuels
        for key, pattern in COMPILE_CHAT_PATTERNS.items():
            match = pattern.search(line)
            if match:
                try:
                    value = int(match.group(1))
                    if key == 'tools':
                        metrics.tools_tokens = value
                    elif key == 'system_message':
                        metrics.system_message_tokens = value
                    elif key == 'context_length':
                        metrics.context_length = value
                    found = True
                except (ValueError, IndexError):
                    continue
        
        # Calcul du total si on a des composants séparés
        components = [
            metrics.prompt_tokens,
            metrics.completion_tokens,
            metrics.tools_tokens,
            metrics.system_message_tokens
        ]
        
        if any(components):
            calculated_total = sum(c for c in components if c > 0)
            if calculated_total > 0:
                if metrics.total_tokens > 0:
                    metrics.total_tokens = max(metrics.total_tokens, calculated_total)
                else:
                    metrics.total_tokens = calculated_total
                found = True
        
        return metrics if found else None
    
    def _parse_compile_chat_block(self) -> Optional[TokenMetrics]:
        """Parse le bloc CompileChat accumulé."""
        if not self._compile_chat_buffer:
            return None
        
        block_text = '\n'.join(self._compile_chat_buffer)
        
        metrics = TokenMetrics(
            source="logs",
            raw_line=block_text[:300],
            is_compile_chat=True,
            is_api_error=False
        )
        
        found = False
        
        # Parse chaque ligne du bloc
        for line in self._compile_chat_buffer:
            for key, pattern in COMPILE_CHAT_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    try:
                        value = int(match.group(1))
                        if key == 'tools':
                            metrics.tools_tokens = value
                        elif key == 'system_message':
                            metrics.system_message_tokens = value
                        elif key == 'context_length':
                            metrics.context_length = value
                        found = True
                    except (ValueError, IndexError):
                        continue
        
        # Calcule le total à partir des composants
        if found:
            total = (
                metrics.tools_tokens +
                metrics.system_message_tokens +
                metrics.prompt_tokens
            )
            
            if metrics.context_length > 0:
                metrics.total_tokens = min(total, metrics.context_length)
            else:
                metrics.total_tokens = total
        
        self._compile_chat_buffer = []
        return metrics if found else None
    
    def reset(self):
        """Réinitialise l'état du parser."""
        self._compile_chat_buffer = []
        self._in_compile_chat_block = False


def parse_token_metrics(line: str) -> Optional[Dict[str, Any]]:
    """
    Fonction utilitaire pour parser une ligne de log.
    
    Args:
        line: Ligne de log
        
    Returns:
        Dictionnaire des métriques ou None
    """
    parser = LogParser()
    metrics = parser.parse_line(line)
    return metrics.to_dict() if metrics else None
