"""
Rate Limiter pour contrôler le nombre de requêtes par minute.
"""
import time
import asyncio
from collections import deque
from typing import Optional, Dict, Any

from ..core.constants import (
    MAX_RPM,
    RATE_LIMIT_WARNING_THRESHOLD,
    RATE_LIMIT_CRITICAL_THRESHOLD
)


class RateLimiter:
    """Limite le nombre de requêtes par minute (RPM)."""
    
    def __init__(self, max_rpm: int = MAX_RPM):
        self.max_rpm = max_rpm
        self.warning_threshold = int(max_rpm * RATE_LIMIT_WARNING_THRESHOLD)
        self.critical_threshold = int(max_rpm * RATE_LIMIT_CRITICAL_THRESHOLD)
        self.requests: deque = deque()
        self.lock = asyncio.Lock()
        self.total_throttled = 0
    
    def _clean_old_requests(self):
        """Supprime les requêtes de plus de 60 secondes."""
        now = time.time()
        cutoff = now - 60
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def get_current_rpm(self) -> float:
        """Retourne le nombre de requêtes dans la dernière minute."""
        self._clean_old_requests()
        return len(self.requests)
    
    def get_rpm_percentage(self) -> float:
        """Retourne le pourcentage du rate limit utilisé."""
        return (self.get_current_rpm() / self.max_rpm) * 100
    
    async def acquire(self, wait_if_needed: bool = True) -> Dict[str, Any]:
        """
        Acquiert une "place" pour faire une requête.
        
        Args:
            wait_if_needed: Si True, attend si le rate limit est critique
            
        Returns:
            Dictionnaire avec le statut de l'acquisition
        """
        async with self.lock:
            self._clean_old_requests()
            current_rpm = len(self.requests)
            
            status = {
                "allowed": True,
                "current_rpm": current_rpm,
                "max_rpm": self.max_rpm,
                "percentage": (current_rpm / self.max_rpm) * 100,
                "throttled": False,
                "wait_time": 0
            }
            
            if current_rpm >= self.critical_threshold:
                if wait_if_needed:
                    oldest_request = self.requests[0]
                    wait_time = 60 - (time.time() - oldest_request) + 0.1
                    status["wait_time"] = max(0.1, wait_time)
                    status["throttled"] = True
                    self.total_throttled += 1
                else:
                    status["allowed"] = False
                    return status
            
            self.requests.append(time.time())
            return status
    
    async def throttle_if_needed(self) -> Dict[str, Any]:
        """
        Vérifie et attend si nécessaire pour respecter le rate limit.
        
        Returns:
            Statut final après throttle éventuel
        """
        status = await self.acquire(wait_if_needed=True)
        
        if status["throttled"] and status["wait_time"] > 0:
            print(f"⏱️ Rate limit critique ({status['current_rpm']:.0f} RPM) - "
                  f"Attente {status['wait_time']:.1f}s...")
            await asyncio.sleep(status["wait_time"])
            
            async with self.lock:
                self._clean_old_requests()
                self.requests.append(time.time())
                status["current_rpm"] = len(self.requests)
                status["throttled"] = False
        
        return status
    
    def check_alert(self) -> Optional[str]:
        """
        Vérifie si une alerte de rate limit doit être émise.
        
        Returns:
            Message d'alerte ou None
        """
        rpm = self.get_current_rpm()
        percentage = self.get_rpm_percentage()
        
        if rpm >= self.critical_threshold:
            return f"🚨 RATE LIMIT CRITIQUE: {rpm:.0f}/{self.max_rpm} RPM ({percentage:.1f}%)"
        elif rpm >= self.warning_threshold:
            return f"⚠️ Rate limit élevé: {rpm:.0f}/{self.max_rpm} RPM ({percentage:.1f}%)"
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du rate limiter."""
        return {
            "current_rpm": self.get_current_rpm(),
            "max_rpm": self.max_rpm,
            "percentage": round(self.get_rpm_percentage(), 1),
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "total_throttled": self.total_throttled
        }


# Instance globale
_limiter: Optional[RateLimiter] = None


def create_rate_limiter(max_rpm: int = MAX_RPM) -> RateLimiter:
    """
    Crée ou retourne l'instance globale du rate limiter.
    
    Args:
        max_rpm: Nombre maximum de requêtes par minute
        
    Returns:
        Instance de RateLimiter
    """
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(max_rpm=max_rpm)
    return _limiter


def get_rate_limiter() -> RateLimiter:
    """Alias de create_rate_limiter."""
    return create_rate_limiter()
