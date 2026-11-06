"""Exceptions personnalisées du middleware Kimi Proxy MCP."""
from typing import Optional


class KimiProxyError(Exception):
    """Exception de base pour toutes les erreurs du proxy."""

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code or "unknown_error"
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"[{self.code}] {self.message} - Détails: {self.details}"
        return f"[{self.code}] {self.message}"


class ConfigurationError(KimiProxyError):
    """Erreur de configuration (fichier manquant, valeur invalide)."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message=message,
            code="config_error",
            details={"key": config_key} if config_key else {},
        )


class TokenizationError(KimiProxyError):
    """Erreur lors du comptage de tokens."""

    def __init__(self, message: str, content_preview: Optional[str] = None):
        details = {}
        if content_preview:
            details["preview"] = content_preview[:100]
        super().__init__(
            message=message,
            code="tokenization_error",
            details=details,
        )


class CompactionError(KimiProxyError):
    """Erreur lors de la compaction du contexte."""

    def __init__(self, message: str, session_id: Optional[int] = None):
        super().__init__(
            message=message,
            code="compaction_error",
            details={"session_id": session_id} if session_id else {},
        )
