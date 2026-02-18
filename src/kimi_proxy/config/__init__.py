"""
Configuration du Kimi Proxy Dashboard.
"""

from .loader import load_config, reload_config
from .settings import Settings, SanitizerConfig, CompressionConfig
from .display import (
    get_provider_display_name,
    get_provider_icon,
    get_provider_color,
    get_model_display_name,
)

__all__ = [
    "load_config",
    "reload_config",
    "Settings",
    "SanitizerConfig",
    "CompressionConfig",
    "get_provider_display_name",
    "get_provider_icon",
    "get_provider_color",
    "get_model_display_name",
]
