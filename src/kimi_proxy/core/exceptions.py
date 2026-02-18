"""
Exceptions personnalisées pour Kimi Proxy Dashboard.
"""


class KimiProxyError(Exception):
    """Exception de base pour toutes les erreurs du proxy."""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
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
    
    def __init__(self, message: str, config_key: str = None):
        super().__init__(
            message=message,
            code="config_error",
            details={"key": config_key} if config_key else {}
        )


class ProviderError(KimiProxyError):
    """Erreur liée à un provider (clé API manquante, URL invalide)."""
    
    def __init__(self, message: str, provider: str = None):
        super().__init__(
            message=message,
            code="provider_error",
            details={"provider": provider} if provider else {}
        )


class DatabaseError(KimiProxyError):
    """Erreur de base de données SQLite."""
    
    def __init__(self, message: str, operation: str = None):
        super().__init__(
            message=message,
            code="database_error",
            details={"operation": operation} if operation else {}
        )


class TokenizationError(KimiProxyError):
    """Erreur lors du comptage de tokens."""
    
    def __init__(self, message: str, content_preview: str = None):
        details = {}
        if content_preview:
            details["preview"] = content_preview[:100]
        super().__init__(
            message=message,
            code="tokenization_error",
            details=details
        )


class RateLimitError(KimiProxyError):
    """Erreur de rate limiting dépassé."""
    
    def __init__(self, message: str, current_rpm: int = None, max_rpm: int = None):
        super().__init__(
            message=message,
            code="rate_limit_error",
            details={
                "current_rpm": current_rpm,
                "max_rpm": max_rpm
            }
        )


class CompressionError(KimiProxyError):
    """Erreur lors de la compression d'historique."""
    
    def __init__(self, message: str, session_id: int = None):
        super().__init__(
            message=message,
            code="compression_error",
            details={"session_id": session_id} if session_id else {}
        )


class CompactionError(KimiProxyError):
    """Erreur lors de la compaction du contexte."""
    
    def __init__(self, message: str, session_id: int = None):
        super().__init__(
            message=message,
            code="compaction_error",
            details={"session_id": session_id} if session_id else {}
        )


class StreamingError(KimiProxyError):
    """Erreur lors du streaming de réponse provider."""
    
    def __init__(
        self, 
        message: str, 
        provider: str = None,
        error_type: str = None,
        retry_count: int = 0,
        details: dict = None
    ):
        super().__init__(
            message=message,
            code="streaming_error",
            details={
                "provider": provider,
                "error_type": error_type,
                "retry_count": retry_count,
                **(details or {})
            }
        )
        self.error_type = error_type
        self.retry_count = retry_count
