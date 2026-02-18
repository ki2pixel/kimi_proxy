"""
Routes API pour le health check.
"""
from fastapi import APIRouter

from ...core.database import get_active_session
from ...config.display import get_max_context_for_session
from ...config.loader import get_config
from ...services.rate_limiter import get_rate_limiter
from ...features.log_watcher import LogWatcher

# Instance globale du log watcher (sera injectée depuis main.py)
_log_watcher: LogWatcher = None

router = APIRouter()


def set_log_watcher(watcher: LogWatcher):
    """Définit l'instance du log watcher pour le health check."""
    global _log_watcher
    _log_watcher = watcher


@router.get("/health")
async def health_check():
    """Health check avec infos sur la session et le log watcher."""
    import os
    
    config = get_config()
    models = config.get("models", {})
    
    session = get_active_session()
    max_context = get_max_context_for_session(session, models)
    
    # Vérifie si le log watcher est actif
    log_watcher_status = "running" if _log_watcher and _log_watcher.running else "stopped"
    log_file_exists = os.path.exists(_log_watcher.log_path) if _log_watcher else False
    
    rate_limiter = get_rate_limiter()
    
    return {
        "status": "ok",
        "max_context": max_context,
        "active_session": session,
        "log_watcher": {
            "status": log_watcher_status,
            "log_file_exists": log_file_exists,
            "log_path": _log_watcher.log_path if _log_watcher else None
        },
        "rate_limit": {
            "current_rpm": rate_limiter.get_current_rpm(),
            "max_rpm": rate_limiter.max_rpm,
            "percentage": round(rate_limiter.get_rpm_percentage(), 1)
        }
    }


@router.get("/api/rate-limit")
async def get_rate_limit_status():
    """Retourne le statut du rate limiting."""
    rate_limiter = get_rate_limiter()
    rpm = rate_limiter.get_current_rpm()
    percentage = rate_limiter.get_rpm_percentage()
    
    status = "normal"
    if rpm >= rate_limiter.critical_threshold:
        status = "critical"
    elif rpm >= rate_limiter.warning_threshold:
        status = "warning"
    elif rpm >= rate_limiter.max_rpm * 0.5:
        status = "elevated"
    
    return {
        "status": status,
        "current_rpm": rpm,
        "max_rpm": rate_limiter.max_rpm,
        "percentage": round(percentage, 1)
    }
