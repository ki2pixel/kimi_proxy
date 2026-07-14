"""
Service de déclenchement automatique de compaction - Phase 2.

Gère les triggers automatiques basés sur les seuils de contexte
avec support par session et cooldown entre compactions.
"""
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable

from ...config.loader import get_config
from ...core.database import (
    get_session_compaction_state,
    increment_consecutive_auto_compactions,
    reset_consecutive_auto_compactions,
    get_session_by_id,
)
from ...core.exceptions import CompactionError
from .simple_compaction import SimpleCompaction, CompactionConfig, CompactionResult
from .storage import persist_compaction_result


@dataclass
class AutoTriggerConfig:
    """Configuration pour les triggers automatiques."""
    enabled: bool = True
    threshold: float = 0.85  # 85% du contexte
    cooldown_minutes: int = 5
    max_consecutive: int = 3
    min_tokens: int = 500
    min_messages: int = 6
    
    @classmethod
    def from_config(cls) -> "AutoTriggerConfig":
        """Charge la configuration depuis config.toml."""
        config = get_config()
        compaction = config.get("compaction", {})
        auto = compaction.get("auto", {})
        
        return cls(
            enabled=auto.get("auto_compact", True),
            threshold=auto.get("auto_compact_threshold", 0.85),
            cooldown_minutes=auto.get("auto_compact_cooldown", 5),
            max_consecutive=auto.get("max_consecutive_auto_compactions", 3),
            min_tokens=compaction.get("min_tokens_to_compact", 500),
            min_messages=compaction.get("min_messages_to_compact", 6)
        )


class CompactionAutoTrigger:
    """
    Gestionnaire de déclenchement automatique de compaction.
    
    Surveille l'utilisation du contexte et déclenche la compaction
    automatique quand les seuils sont atteints.
    """
    
    def __init__(self):
        self.config = AutoTriggerConfig.from_config()
        self._last_check: Dict[int, float] = {}  # session_id -> timestamp
        self._cooldown_until: Dict[int, float] = {}  # session_id -> timestamp
        self._pending_compactions: set = set()
    
    async def check_and_trigger(
        self,
        session_id: int,
        current_tokens: int,
        max_context: int,
        messages: list,
        trigger_callback: Optional[Callable] = None
    ) -> Optional[CompactionResult]:
        """
        Vérifie si une compaction doit être déclenchée et l'exécute si nécessaire.
        
        Args:
            session_id: ID de la session
            current_tokens: Nombre de tokens actuels (cumulés pour le seuil)
            max_context: Taille maximale du contexte
            messages: Messages de la session
            trigger_callback: Callback optionnel appelé après déclenchement
            
        Returns:
            Résultat de la compaction si déclenchée, None sinon
        """
        if not self.config.enabled:
            return None
        
        # Vérifie si une compaction est déjà en cours pour cette session
        if session_id in self._pending_compactions:
            return None
        
        # Récupère l'état de la session
        session = get_session_by_id(session_id)
        if not session:
            return None
        
        # Vérifie si l'auto-compaction est activée pour cette session
        compaction_state = get_session_compaction_state(session_id)
        if not compaction_state.get("auto_compaction_enabled", True):
            return None
        
        # Utilise le seuil personnalisé de la session ou celui par défaut
        threshold = compaction_state.get("auto_compaction_threshold", self.config.threshold)
        
        # Vérifie si le seuil est atteint - utilise current_tokens (qui devrait être cumulés)
        usage_ratio = current_tokens / max_context if max_context > 0 else 0
        if usage_ratio < threshold:
            return None
        
        # Vérifie le cooldown
        now = time.time()
        if session_id in self._cooldown_until:
            if now < self._cooldown_until[session_id]:
                return None
        
        # Vérifie le nombre de compactions consécutives
        consecutive = compaction_state.get("consecutive_auto_compactions", 0)
        if consecutive >= self.config.max_consecutive:
            return None
        
        # Vérifie les minimums
        if len(messages) < self.config.min_messages:
            return None
        if current_tokens < self.config.min_tokens:
            return None
        
        # Marque comme compaction en cours
        self._pending_compactions.add(session_id)
        
        try:
            # Exécute la compaction
            result = await self._execute_auto_compaction(
                session_id, messages, compaction_state
            )
            
            if result and result.compacted:
                # Met à jour le cooldown
                cooldown_seconds = self.config.cooldown_minutes * 60
                self._cooldown_until[session_id] = now + cooldown_seconds
                
                # Incrémente le compteur de compactions consécutives
                new_count = increment_consecutive_auto_compactions(session_id)
                
                # Appelle le callback si fourni
                if trigger_callback:
                    await trigger_callback(result, {
                        "threshold": threshold,
                        "usage_ratio": usage_ratio,
                        "consecutive_count": new_count
                    })
                
                return result
            else:
                # Si la compaction n'a pas eu lieu, réinitialise le compteur
                reset_consecutive_auto_compactions(session_id)
                
        except Exception as e:
            raise CompactionError(
                message=f"Erreur auto-compaction session {session_id}: {e}",
                session_id=session_id
            )
        finally:
            self._pending_compactions.discard(session_id)
        
        return None
    
    async def _execute_auto_compaction(
        self,
        session_id: int,
        messages: list,
        compaction_state: Dict[str, Any]
    ) -> Optional[CompactionResult]:
        """
        Exécute la compaction automatique.
        
        Args:
            session_id: ID de la session
            messages: Messages à compacter
            compaction_state: État de compaction de la session
            
        Returns:
            Résultat de la compaction
        """
        # Crée le compacteur avec la configuration
        config = CompactionConfig(
            max_preserved_messages=2,  # Préserve 2 échanges par défaut
            min_messages_to_compact=self.config.min_messages,
            min_tokens_to_compact=self.config.min_tokens
        )
        compactor = SimpleCompaction(config)
        
        # Vérifie si la compaction est nécessaire
        should_compact, reason = compactor.should_compact(messages)
        if not should_compact:
            return CompactionResult(
                compacted=False,
                session_id=session_id,
                messages_before=len(messages),
                messages_after=len(messages),
                reason=reason
            )
        
        # Exécute la compaction
        result = compactor.compact(messages, session_id=session_id)
        
        if result.compacted:
            # Persiste le résultat
            await persist_compaction_result(result, trigger_reason="auto_threshold")
        
        return result
    
    def should_warn_threshold(
        self,
        session_id: int,
        current_tokens: int,
        max_context: int
    ) -> Optional[Dict[str, Any]]:
        """
        Vérifie si une alerte de seuil doit être émise.
        
        Args:
            session_id: ID de la session
            current_tokens: Nombre de tokens actuels
            max_context: Taille maximale du contexte
            
        Returns:
            Informations d'alerte si un seuil est atteint, None sinon
        """
        usage_ratio = current_tokens / max_context if max_context > 0 else 0
        percentage = usage_ratio * 100
        
        # Seuils d'alerte (avant déclenchement)
        config = get_config()
        compaction = config.get("compaction", {})
        threshold_percentage = compaction.get("threshold_percentage", 80)
        
        if percentage >= 95:
            return {
                "level": "critical",
                "message": "🚨 Contexte critique - Compaction imminente",
                "percentage": percentage,
                "tokens": current_tokens,
                "max_context": max_context,
                "action_recommended": "compact_now"
            }
        elif percentage >= threshold_percentage:
            return {
                "level": "warning",
                "message": f"⚠️ Seuil compaction atteint ({threshold_percentage}%)",
                "percentage": percentage,
                "tokens": current_tokens,
                "max_context": max_context,
                "action_recommended": "prepare_compact"
            }
        elif percentage >= 70:
            return {
                "level": "info",
                "message": "ℹ️ Contexte élevé - Surveillance active",
                "percentage": percentage,
                "tokens": current_tokens,
                "max_context": max_context,
                "action_recommended": "monitor"
            }
        
        return None
    
    def reset_session(self, session_id: int):
        """
        Réinitialise l'état d'une session (appelé après nouvelle session).
        
        Args:
            session_id: ID de la session
        """
        self._last_check.pop(session_id, None)
        self._cooldown_until.pop(session_id, None)
        self._pending_compactions.discard(session_id)
        reset_consecutive_auto_compactions(session_id)
    
    def get_status(self, session_id: int) -> Dict[str, Any]:
        """
        Retourne le statut du trigger pour une session.
        
        Args:
            session_id: ID de la session
            
        Returns:
            Statut complet du trigger
        """
        now = time.time()
        compaction_state = get_session_compaction_state(session_id)
        
        cooldown_until = self._cooldown_until.get(session_id, 0)
        cooldown_remaining = max(0, cooldown_until - now)
        
        return {
            "enabled": self.config.enabled,
            "session_auto_enabled": compaction_state.get("auto_compaction_enabled", True),
            "threshold": compaction_state.get("auto_compaction_threshold", self.config.threshold),
            "cooldown_minutes": self.config.cooldown_minutes,
            "cooldown_remaining_seconds": cooldown_remaining,
            "max_consecutive": self.config.max_consecutive,
            "consecutive_count": compaction_state.get("consecutive_auto_compactions", 0),
            "is_pending": session_id in self._pending_compactions,
            "last_compaction_at": compaction_state.get("last_compaction_at"),
            "total_compactions": compaction_state.get("compaction_count", 0)
        }


# Instance globale
_auto_trigger: Optional[CompactionAutoTrigger] = None


def get_auto_trigger() -> CompactionAutoTrigger:
    """Retourne l'instance globale du gestionnaire de triggers."""
    global _auto_trigger
    if _auto_trigger is None:
        _auto_trigger = CompactionAutoTrigger()
    return _auto_trigger
