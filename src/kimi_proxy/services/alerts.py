"""
Gestion des alertes et seuils.
"""
from typing import Optional, Dict, Any

from ..core.constants import ALERT_THRESHOLDS


class AlertManager:
    """Gère les alertes de seuils de contexte."""
    
    def __init__(self):
        self.thresholds = ALERT_THRESHOLDS
        self.last_alert_level: Optional[str] = None
    
    def check_threshold(self, percentage: float) -> Optional[Dict[str, Any]]:
        """
        Vérifie si un seuil d'alerte est atteint.
        
        Args:
            percentage: Pourcentage du contexte utilisé
            
        Returns:
            Dictionnaire d'alerte ou None
        """
        if percentage >= self.thresholds["critical"]:
            return {
                "level": "critical",
                "color": "#ef4444",
                "message": f"⚠️ CONTEXTE CRITIQUE ({percentage:.0f}%)",
                "threshold": self.thresholds["critical"]
            }
        elif percentage >= self.thresholds["warning"]:
            return {
                "level": "warning",
                "color": "#f97316",
                "message": f"⚠️ CONTEXTE ÉLEVÉ ({percentage:.0f}%)",
                "threshold": self.thresholds["warning"]
            }
        elif percentage >= self.thresholds["caution"]:
            return {
                "level": "caution",
                "color": "#eab308",
                "message": f"⚡ Attention ({percentage:.0f}%)",
                "threshold": self.thresholds["caution"]
            }
        return None
    
    def should_notify(self, percentage: float) -> bool:
        """
        Détermine si une notification doit être envoyée.
        Évite les notifications répétées pour le même niveau.
        
        Args:
            percentage: Pourcentage du contexte utilisé
            
        Returns:
            True si une notification doit être envoyée
        """
        current_level = None
        
        if percentage >= self.thresholds["critical"]:
            current_level = "critical"
        elif percentage >= self.thresholds["warning"]:
            current_level = "warning"
        elif percentage >= self.thresholds["caution"]:
            current_level = "caution"
        
        # Notifie si le niveau change ou si c'est critique
        should_notify = (
            current_level != self.last_alert_level or 
            current_level == "critical"
        )
        
        self.last_alert_level = current_level
        return should_notify
    
    def reset(self):
        """Réinitialise l'état des alertes."""
        self.last_alert_level = None


def check_threshold_alert(percentage: float) -> Optional[Dict[str, Any]]:
    """
    Fonction utilitaire pour vérifier les seuils.
    
    Args:
        percentage: Pourcentage du contexte utilisé
        
    Returns:
        Dictionnaire d'alerte ou None
    """
    if percentage >= 95:
        return {
            "level": "critical",
            "color": "#ef4444",
            "message": "⚠️ CONTEXTE CRITIQUE (95%)"
        }
    elif percentage >= 90:
        return {
            "level": "warning",
            "color": "#f97316",
            "message": "⚠️ CONTEXTE ÉLEVÉ (90%)"
        }
    elif percentage >= 80:
        return {
            "level": "caution",
            "color": "#eab308",
            "message": "⚡ Attention (80%)"
        }
    return None


def format_alert_message(level: str, percentage: float) -> str:
    """Formate un message d'alerte."""
    alerts = {
        "critical": f"🚨 CONTEXTE CRITIQUE: {percentage:.1f}%",
        "warning": f"⚠️ CONTEXTE ÉLEVÉ: {percentage:.1f}%",
        "caution": f"⚡ Attention: {percentage:.1f}%"
    }
    return alerts.get(level, f"Niveau: {level} - {percentage:.1f}%")
