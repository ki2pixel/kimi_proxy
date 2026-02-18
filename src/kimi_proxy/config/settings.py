"""
Dataclasses pour la configuration.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class SanitizerConfig:
    """Configuration du sanitizer."""
    enabled: bool = True
    threshold_tokens: int = 1000
    preview_length: int = 200
    tmp_dir: str = "/tmp/kimi_proxy_masked"
    tags: List[str] = field(default_factory=lambda: ["@file", "@codebase", "@tool", "@console", "@output"])
    fallback_threshold: float = 0.90
    heavy_duty_fallback: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SanitizerConfig":
        """Crée une instance depuis un dictionnaire."""
        return cls(
            enabled=data.get("enabled", True),
            threshold_tokens=data.get("threshold_tokens", 1000),
            preview_length=data.get("preview_length", 200),
            tmp_dir=data.get("tmp_dir", "/tmp/kimi_proxy_masked"),
            tags=data.get("tags", ["@file", "@codebase", "@tool", "@console", "@output"]),
            fallback_threshold=data.get("fallback_threshold", 0.90),
            heavy_duty_fallback=data.get("heavy_duty_fallback", True)
        )


@dataclass
class CompressionConfig:
    """Configuration de compression."""
    enabled: bool = True
    threshold_percentage: int = 85
    preserve_recent_exchanges: int = 5
    summary_max_tokens: int = 500
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompressionConfig":
        """Crée une instance depuis un dictionnaire."""
        return cls(
            enabled=data.get("enabled", True),
            threshold_percentage=data.get("threshold_percentage", 85),
            preserve_recent_exchanges=data.get("preserve_recent_exchanges", 5),
            summary_max_tokens=data.get("summary_max_tokens", 500)
        )


@dataclass
class RateLimitConfig:
    """Configuration du rate limiting."""
    max_rpm: int = 40
    warning_threshold: float = 0.875
    critical_threshold: float = 0.95
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RateLimitConfig":
        """Crée une instance depuis un dictionnaire."""
        return cls(
            max_rpm=data.get("max_rpm", 40),
            warning_threshold=data.get("warning_threshold", 0.875),
            critical_threshold=data.get("critical_threshold", 0.95)
        )


@dataclass
class Settings:
    """Configuration globale de l'application."""
    default_provider: str = "managed:kimi-code"
    default_max_context: int = 262144
    database_file: str = "sessions.db"
    sanitizer: SanitizerConfig = field(default_factory=SanitizerConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    models: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "Settings":
        """Crée une instance depuis la configuration chargée."""
        from .loader import init_providers, init_models, get_sanitizer_config, get_compression_config
        
        return cls(
            default_provider=config.get("default_model", "managed:kimi-code"),
            default_max_context=262144,
            database_file="sessions.db",
            sanitizer=SanitizerConfig.from_dict(get_sanitizer_config(config)),
            compression=CompressionConfig.from_dict(get_compression_config(config)),
            providers=init_providers(config),
            models=init_models(config)
        )
    
    def get_provider(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupère un provider par sa clé."""
        return self.providers.get(key)
    
    def get_model(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupère un modèle par sa clé."""
        return self.models.get(key)
    
    def get_models_for_provider(self, provider_key: str) -> List[Dict[str, Any]]:
        """Récupère tous les modèles d'un provider."""
        return [
            model for model in self.models.values()
            if model.get("provider") == provider_key
        ]
