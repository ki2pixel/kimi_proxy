"""
Chargement de la configuration TOML.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional

from ..core.exceptions import ConfigurationError

# Cache global de configuration
_config_cache: Optional[Dict[str, Any]] = None


def _expand_env_vars(obj: Any) -> Any:
    """
    Récursivement étend les variables d'environnement ${VAR} dans la config.
    
    Args:
        obj: Valeur à traiter (str, dict, list)
        
    Returns:
        Valeur avec variables d'environnement expansiées
    """
    if isinstance(obj, str):
        # Remplace ${VAR} par la valeur de l'environnement
        import re
        def replace_env_var(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return re.sub(r'\$\{([^}]+)\}', replace_env_var, obj)
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


def _clear_config_cache():
    """Vide le cache de configuration."""
    global _config_cache
    _config_cache = None


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Charge la configuration depuis config.toml.
    
    Args:
        config_path: Chemin vers le fichier config (optionnel)
        
    Returns:
        Dictionnaire de configuration
        
    Raises:
        ConfigurationError: Si le fichier n'existe pas ou est invalide
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    if config_path is None:
        # Cherche config.toml dans le répertoire projet (parent de src/)
        # Structure: project/src/kimi_proxy/config/loader.py
        current_file = os.path.abspath(__file__)
        # Remonte de 4 niveaux: loader.py -> config -> kimi_proxy -> src -> project
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        config_path = os.path.join(project_dir, "config.toml")
    
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(
            message=f"Fichier de configuration non trouvé: {config_path}",
            config_key="config_path"
        )
    
    try:
        import tomllib
        with open(path, "rb") as f:
            raw_config = tomllib.load(f)
            _config_cache = _expand_env_vars(raw_config)
    except ImportError:
        try:
            import tomli
            with open(path, "rb") as f:
                raw_config = tomli.load(f)
                _config_cache = _expand_env_vars(raw_config)
        except ImportError:
            raise ConfigurationError(
                message="tomllib ou tomli requis pour charger la configuration",
                config_key="dependencies"
            )
    
    return _config_cache


def reload_config(config_path: str = None) -> Dict[str, Any]:
    """
    Recharge la configuration depuis le fichier.
    
    Returns:
        Nouvelle configuration chargée
    """
    global _config_cache
    _config_cache = None
    return load_config(config_path)


def get_config() -> Dict[str, Any]:
    """
    Retourne la configuration en cache.
    
    Returns:
        Configuration actuelle
    """
    global _config_cache
    if _config_cache is None:
        return load_config()
    return _config_cache


def init_providers(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Initialise les providers depuis la configuration.
    
    Args:
        config: Configuration chargée
        
    Returns:
        Dictionnaire des providers
    """
    providers = {}
    providers_config = config.get("providers", {})
    
    for provider_key, provider_data in providers_config.items():
        providers[provider_key] = {
            "key": provider_key,
            "type": provider_data.get("type", "openai"),
            "base_url": provider_data.get("base_url", ""),
            "api_key": provider_data.get("api_key", "")
        }
    
    return providers


def init_models(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Initialise les modèles depuis la configuration.
    
    Args:
        config: Configuration chargée
        
    Returns:
        Dictionnaire des modèles
    """
    models = {}
    models_config = config.get("models", {})
    
    for model_key, model_data in models_config.items():
        provider = model_data.get("provider", "nvidia")
        models[model_key] = {
            "key": model_key,
            "model": model_data.get("model", model_key),
            "provider": provider,
            "max_context_size": model_data.get("max_context_size", 262144),
            "capabilities": model_data.get("capabilities", [])
        }
    
    return models


def get_sanitizer_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait la configuration du sanitizer.
    
    Args:
        config: Configuration chargée
        
    Returns:
        Configuration du sanitizer
    """
    from ..core.constants import DEFAULT_SANITIZER_CONFIG
    
    sanitizer_config = config.get("sanitizer", {})
    return {
        "enabled": sanitizer_config.get("enabled", DEFAULT_SANITIZER_CONFIG["enabled"]),
        "threshold_tokens": sanitizer_config.get("threshold_tokens", DEFAULT_SANITIZER_CONFIG["threshold_tokens"]),
        "preview_length": sanitizer_config.get("preview_length", DEFAULT_SANITIZER_CONFIG["preview_length"]),
        "tmp_dir": sanitizer_config.get("tmp_dir", DEFAULT_SANITIZER_CONFIG["tmp_dir"]),
        "tags": sanitizer_config.get("trigger_tags", DEFAULT_SANITIZER_CONFIG["tags"]),
        "fallback_threshold": sanitizer_config.get("routing", {}).get("fallback_threshold", 0.90),
        "heavy_duty_fallback": sanitizer_config.get("routing", {}).get("heavy_duty_fallback", True),
    }


def get_compression_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait la configuration de compression.
    
    Args:
        config: Configuration chargée
        
    Returns:
        Configuration de compression
    """
    from ..core.constants import DEFAULT_COMPRESSION_CONFIG
    
    return {
        "enabled": DEFAULT_COMPRESSION_CONFIG["enabled"],
        "threshold_percentage": DEFAULT_COMPRESSION_CONFIG["threshold_percentage"],
        "preserve_recent_exchanges": DEFAULT_COMPRESSION_CONFIG["preserve_recent_exchanges"],
        "summary_max_tokens": DEFAULT_COMPRESSION_CONFIG["summary_max_tokens"],
    }
