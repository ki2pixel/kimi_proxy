"""
Service SimpleCompaction - Phase 1 Infrastructure de Base.

Implémentation inspirée de Kimi CLI pour la compaction automatique
du contexte LLM avec préservation configurable des messages récents.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from ...core.tokens import count_tokens_tiktoken, count_tokens_text
from ...core.constants import DEFAULT_COMPACTION_CONFIG
from ...core.exceptions import CompactionError


@dataclass
class CompactionResult:
    """Résultat d'une opération de compaction."""
    compacted: bool
    session_id: int = 0
    original_tokens: int = 0
    compacted_tokens: int = 0
    tokens_saved: int = 0
    compaction_ratio: float = 0.0
    messages_before: int = 0
    messages_after: int = 0
    system_preserved: int = 0
    recent_preserved: int = 0
    summarized_count: int = 0
    summary_text: Optional[str] = None
    error: Optional[str] = None
    reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat en dictionnaire."""
        result = {
            "compacted": self.compacted,
            "session_id": self.session_id,
            "original_tokens": self.original_tokens,
            "compacted_tokens": self.compacted_tokens,
            "tokens_saved": self.tokens_saved,
            "compaction_ratio": round(self.compaction_ratio, 2),
            "messages_before": self.messages_before,
            "messages_after": self.messages_after,
            "system_preserved": self.system_preserved,
            "recent_preserved": self.recent_preserved,
            "summarized_count": self.summarized_count,
            "timestamp": self.timestamp
        }
        if self.summary_text:
            result["summary_text"] = self.summary_text[:500]  # Limite la taille
        if self.error:
            result["error"] = self.error
        if self.reason:
            result["reason"] = self.reason
        return result


@dataclass
class CompactionConfig:
    """Configuration pour la compaction."""
    max_preserved_messages: int = 2  # Nombre d'échanges récents à préserver (2 = 4 messages)
    preserve_system_messages: bool = True
    create_summary: bool = True
    summary_max_length: int = 1000  # Caractères
    min_messages_to_compact: int = 6  # Minimum de messages pour déclencher
    min_tokens_to_compact: int = 500  # Minimum de tokens pour déclencher
    target_reduction_ratio: float = 0.60  # Objectif de réduction (60%)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_preserved_messages": self.max_preserved_messages,
            "preserve_system_messages": self.preserve_system_messages,
            "create_summary": self.create_summary,
            "summary_max_length": self.summary_max_length,
            "min_messages_to_compact": self.min_messages_to_compact,
            "min_tokens_to_compact": self.min_tokens_to_compact,
            "target_reduction_ratio": self.target_reduction_ratio
        }


class SimpleCompaction:
    """
    Service de compaction simple du contexte LLM.
    
    Stratégie:
    1. Préserve tous les messages système
    2. Garde les N derniers échanges (configurable)
    3. Résume les messages intermédiaires en un message de contexte
    4. Calculs précis avec Tiktoken
    
    Inspiré de l'implémentation Kimi CLI.
    """
    
    def __init__(self, config: Optional[CompactionConfig] = None):
        """
        Initialise le service de compaction.
        
        Args:
            config: Configuration personnalisée (optionnel)
        """
        self.config = config or CompactionConfig()
    
    def should_compact(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Détermine si une compaction est nécessaire.
        
        Args:
            messages: Liste des messages à analyser
            current_tokens: Nombre de tokens actuel (calculé si non fourni)
            
        Returns:
            Tuple (should_compact, reason)
        """
        if not messages:
            return False, "no_messages"
        
        if len(messages) < self.config.min_messages_to_compact:
            return False, "insufficient_messages"
        
        # Compte les tokens si nécessaire
        if current_tokens is None:
            current_tokens = count_tokens_tiktoken(messages)
        
        if current_tokens < self.config.min_tokens_to_compact:
            return False, "insufficient_tokens"
        
        # Vérifie s'il y a assez de messages à résumer
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        preserve_count = self.config.max_preserved_messages * 2
        if len(non_system) <= preserve_count:
            return False, "not_enough_messages_to_summarize"
        
        return True, "threshold_reached"
    
    def compact(
        self,
        messages: List[Dict[str, Any]],
        session_id: int = 0,
        current_tokens: Optional[int] = None,
    ) -> CompactionResult:
        """
        Compacte une liste de messages.
        
        Args:
            messages: Liste complète des messages
            session_id: ID de la session (pour le suivi)
            
        Returns:
            Résultat de la compaction
        """
        timestamp = datetime.now().isoformat()
        
        try:
            # Vérifie si la compaction est nécessaire
            should_compact, reason = self.should_compact(messages, current_tokens=current_tokens)
            
            if not should_compact:
                original_tokens = current_tokens if current_tokens is not None else count_tokens_tiktoken(messages)
                return CompactionResult(
                    compacted=False,
                    session_id=session_id,
                    original_tokens=original_tokens,
                    compacted_tokens=original_tokens,
                    messages_before=len(messages),
                    messages_after=len(messages),
                    reason=reason,
                    timestamp=timestamp
                )
            
            # Calcule les tokens avant
            original_tokens = current_tokens if current_tokens is not None else count_tokens_tiktoken(messages)
            
            # Sépare les messages
            system_messages = []
            non_system_messages = []
            
            for msg in messages:
                if msg.get("role") == "system":
                    system_messages.append(msg)
                else:
                    non_system_messages.append(msg)
            
            # Détermine combien de messages récents préserver
            preserve_count = self.config.max_preserved_messages * 2  # user + assistant
            
            if len(non_system_messages) <= preserve_count:
                return CompactionResult(
                    compacted=False,
                    session_id=session_id,
                    original_tokens=original_tokens,
                    compacted_tokens=original_tokens,
                    messages_before=len(messages),
                    messages_after=len(messages),
                    reason="not_enough_messages_to_preserve",
                    timestamp=timestamp
                )
            
            # Messages à préserver (récents)
            recent_messages = non_system_messages[-preserve_count:]
            
            # Messages à résumer (ancien)
            messages_to_summarize = non_system_messages[:-preserve_count]
            
            # Crée le résumé
            summary_message = None
            if self.config.create_summary and messages_to_summarize:
                summary_text = self._create_summary(messages_to_summarize)
                summary_message = {
                    "role": "system",
                    "content": f"[Contexte précédent résumé]\n{summary_text}"
                }
            
            # Construit la liste finale
            compacted_messages = []
            
            # 1. Messages système originaux
            if self.config.preserve_system_messages:
                compacted_messages.extend(system_messages)
            
            # 2. Résumé (si créé)
            if summary_message:
                compacted_messages.append(summary_message)
            
            # 3. Messages récents préservés
            compacted_messages.extend(recent_messages)
            
            # Calcule les résultats
            compacted_tokens = count_tokens_tiktoken(compacted_messages)
            tokens_saved = original_tokens - compacted_tokens
            compaction_ratio = (tokens_saved / original_tokens * 100) if original_tokens > 0 else 0
            
            return CompactionResult(
                compacted=True,
                session_id=session_id,
                original_tokens=original_tokens,
                compacted_tokens=compacted_tokens,
                tokens_saved=tokens_saved,
                compaction_ratio=compaction_ratio,
                messages_before=len(messages),
                messages_after=len(compacted_messages),
                system_preserved=len(system_messages),
                recent_preserved=len(recent_messages),
                summarized_count=len(messages_to_summarize),
                summary_text=summary_message["content"] if summary_message else None,
                timestamp=timestamp
            )
            
        except Exception as e:
            raise CompactionError(
                message=f"Erreur lors de la compaction: {e}",
                session_id=session_id
            )
    
    def _create_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Crée un résumé textuel des messages.
        
        Version simple sans appel LLM - pour l'instant fait un résumé heuristique.
        Dans une implémentation future, pourrait appeler un LLM pour un vrai résumé.
        
        Args:
            messages: Messages à résumer
            
        Returns:
            Texte de résumé
        """
        if not messages:
            return "Aucun message précédent."
        
        # Extrait les échanges clés
        exchanges = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            if isinstance(content, str):
                # Prend un aperçu du contenu
                preview = content[:100].replace("\n", " ")
                if len(content) > 100:
                    preview += "..."
                exchanges.append(f"{role}: {preview}")
        
        # Crée le résumé
        summary_parts = [
            f"Historique de conversation ({len(messages)} messages précédents):"
        ]
        
        # Ajoute les échanges
        for exchange in exchanges[-5:]:  # Limite aux 5 derniers échanges
            summary_parts.append(f"- {exchange}")
        
        # Ajoute des statistiques
        total_tokens = count_tokens_tiktoken(messages)
        summary_parts.append(f"\n[Total: ~{total_tokens} tokens dans l'historique résumé]")
        
        summary = "\n".join(summary_parts)
        
        # Limite la taille
        if len(summary) > self.config.summary_max_length:
            summary = summary[:self.config.summary_max_length - 3] + "..."
        
        return summary
    
    def get_context_with_reserved(
        self,
        messages: List[Dict[str, Any]],
        max_context_size: int,
        reserved_tokens: int = 0
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Retourne le contexte en tenant compte des tokens réservés.
        
        Args:
            messages: Messages complets
            max_context_size: Taille max du contexte
            reserved_tokens: Tokens à réserver pour la compaction
            
        Returns:
            Tuple (messages filtrés, métadonnées)
        """
        available_tokens = max_context_size - reserved_tokens
        current_tokens = count_tokens_tiktoken(messages)
        
        # Si ça rentre, pas besoin de compaction
        if current_tokens <= available_tokens:
            return messages, {
                "compacted": False,
                "reason": "fits_in_context",
                "current_tokens": current_tokens,
                "available_tokens": available_tokens,
                "reserved_tokens": reserved_tokens
            }
        
        # Sinon, compacte
        result = self.compact(messages)
        
        if not result.compacted:
            return messages, {
                "compacted": False,
                "reason": result.reason or "compaction_failed",
                "current_tokens": current_tokens,
                "available_tokens": available_tokens
            }
        
        # Reconstruit les messages compactés
        # (Note: dans une implémentation réelle, on stockerait les messages compactés)
        return messages, {
            "compacted": True,
            "compaction_result": result.to_dict(),
            "recommended_action": "compact_and_retry"
        }


# Instance globale pour usage simple
_default_compactor: Optional[SimpleCompaction] = None


def get_compactor(config: Optional[CompactionConfig] = None) -> SimpleCompaction:
    """
    Retourne l'instance globale du compacteur.
    
    Args:
        config: Configuration optionnelle (utilisée uniquement à la création)
        
    Returns:
        Instance de SimpleCompaction
    """
    global _default_compactor
    if _default_compactor is None:
        _default_compactor = SimpleCompaction(config)
    return _default_compactor


def create_compactor(config: Optional[CompactionConfig] = None) -> SimpleCompaction:
    """
    Crée une nouvelle instance du compacteur.
    
    Args:
        config: Configuration personnalisée
        
    Returns:
        Nouvelle instance de SimpleCompaction
    """
    return SimpleCompaction(config)
