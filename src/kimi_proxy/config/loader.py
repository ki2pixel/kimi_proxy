"""src.kimi_proxy.config.loader

Chargement de la configuration TOML.

Note d'architecture:
- Le package `config/` est consommé par la couche Features.
- Il ne doit donc pas dépendre de `features/*` afin d'éviter les imports circulaires
  et de préserver l'isolation des couches.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Literal

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


@dataclass(frozen=True)
class MCPPrunerBackendConfig:
    """Configuration du serveur MCP Pruner (fallback TOML).

    Règle de priorité:
    - env > toml
    - ce fichier ne contient pas de secrets (API keys restent en env)
    """

    backend: Literal["heuristic", "deepinfra"] = "heuristic"
    deepinfra_timeout_ms: int = 20_000
    deepinfra_max_docs: int = 64
    cache_ttl_s: int = 30
    cache_max_entries: int = 256


def get_mcp_pruner_backend_config(config: Dict[str, Any]) -> MCPPrunerBackendConfig:
    """Charge la config `[mcp_pruner]` depuis le TOML avec fallback robuste.

    Important:
    - Ne doit pas dépendre de `features/*`.
    - N'applique pas la priorité env: cette priorité est gérée au point de consommation.
    """

    defaults = MCPPrunerBackendConfig()
    obj = config.get("mcp_pruner")
    if not isinstance(obj, dict):
        return defaults

    backend_obj = obj.get("backend", defaults.backend)
    backend: Literal["heuristic", "deepinfra"]
    if isinstance(backend_obj, str) and backend_obj.strip().lower() in {"deepinfra", "cloud"}:
        backend = "deepinfra"
    else:
        backend = "heuristic"

    def _clamp_int(value: object, *, default: int, min_value: int, max_value: int) -> int:
        if isinstance(value, int) and not isinstance(value, bool):
            v = value
        elif isinstance(value, float) and not isinstance(value, bool):
            v = int(value)
        else:
            return default
        if v < min_value:
            return min_value
        if v > max_value:
            return max_value
        return v

    deepinfra_timeout_ms = _clamp_int(
        obj.get("deepinfra_timeout_ms", defaults.deepinfra_timeout_ms),
        default=defaults.deepinfra_timeout_ms,
        min_value=1,
        max_value=120_000,
    )
    deepinfra_max_docs = _clamp_int(
        obj.get("deepinfra_max_docs", defaults.deepinfra_max_docs),
        default=defaults.deepinfra_max_docs,
        min_value=1,
        max_value=512,
    )

    cache_ttl_s = _clamp_int(
        obj.get("cache_ttl_s", defaults.cache_ttl_s),
        default=defaults.cache_ttl_s,
        min_value=1,
        max_value=3600,
    )
    cache_max_entries = _clamp_int(
        obj.get("cache_max_entries", defaults.cache_max_entries),
        default=defaults.cache_max_entries,
        min_value=1,
        max_value=100_000,
    )

    return MCPPrunerBackendConfig(
        backend=backend,
        deepinfra_timeout_ms=deepinfra_timeout_ms,
        deepinfra_max_docs=deepinfra_max_docs,
        cache_ttl_s=cache_ttl_s,
        cache_max_entries=cache_max_entries,
    )


@dataclass(frozen=True)
class ObservationMaskingSchema1Config:
    """Configuration Schéma 1 (tool results conversationnels)."""

    enabled: bool = False
    window_turns: int = 8
    keep_errors: bool = True
    keep_last_k_per_tool: int | None = None
    placeholder_template: str = (
        "[Observation masquée: résultat d’outil ancien (tool_call_id={tool_call_id}, "
        "outil={tool_name}, chars={original_chars})]"
    )


def get_observation_masking_schema1_config(config: Dict[str, Any]) -> ObservationMaskingSchema1Config:
    """Charge la configuration Schéma 1 depuis le TOML.

    Propriétés:
    - Fallback robuste si section absente/incomplète
    - Validation/clamp des types pour éviter crash runtime
    - Ne dépend pas de la couche Features
    """

    defaults = ObservationMaskingSchema1Config()
    observation_masking_obj = config.get("observation_masking")
    if not isinstance(observation_masking_obj, dict):
        return defaults

    schema1_obj = observation_masking_obj.get("schema1")
    if not isinstance(schema1_obj, dict):
        return defaults

    enabled_obj = schema1_obj.get("enabled", defaults.enabled)
    enabled = bool(enabled_obj)

    window_turns_obj = schema1_obj.get("window_turns", defaults.window_turns)
    if isinstance(window_turns_obj, int) and not isinstance(window_turns_obj, bool):
        window_turns = max(0, window_turns_obj)
    else:
        window_turns = defaults.window_turns

    keep_errors_obj = schema1_obj.get("keep_errors", defaults.keep_errors)
    keep_errors = bool(keep_errors_obj)

    keep_last_k_obj = schema1_obj.get("keep_last_k_per_tool", defaults.keep_last_k_per_tool)
    keep_last_k: int | None
    if isinstance(keep_last_k_obj, int) and not isinstance(keep_last_k_obj, bool):
        keep_last_k = keep_last_k_obj if keep_last_k_obj > 0 else None
    else:
        keep_last_k = defaults.keep_last_k_per_tool

    placeholder_obj = schema1_obj.get("placeholder_template", defaults.placeholder_template)
    placeholder_template = placeholder_obj if isinstance(placeholder_obj, str) else defaults.placeholder_template

    return ObservationMaskingSchema1Config(
        enabled=enabled,
        window_turns=window_turns,
        keep_errors=keep_errors,
        keep_last_k_per_tool=keep_last_k,
        placeholder_template=placeholder_template,
    )


@dataclass(frozen=True)
class ContextPruningConfig:
    """Configuration d'élagage de contexte via MCP Pruner (Lot C2).

    Objectif: activer un pruning local-first dans le pipeline `/chat/completions`,
    avec rollback instantané (feature flag) et fallback no-op.

    Important:
    - Ce module ne dépend pas de `features/*` (évite imports circulaires).
    - Les champs sont volontairement simples et sérialisables.
    """

    enabled: bool = False

    # Seuil pour éviter d'appeler le pruner sur des messages courts
    min_chars_to_prune: int = 2000

    # Timeout global de l'appel MCP (en ms). En pratique, doit rester court.
    call_timeout_ms: int = 1500

    # Paramètres `options` envoyés à `tools/call` / `prune_text`
    max_prune_ratio: float = 0.55
    min_keep_lines: int = 40
    timeout_ms: int = 1500
    annotate_lines: bool = True
    include_markers: bool = True


def get_context_pruning_config(config: Dict[str, Any]) -> ContextPruningConfig:
    """Charge la configuration `context_pruning` depuis le TOML.

    Propriétés:
    - Fallback robuste si section absente/incomplète
    - Validation/clamp des types pour éviter crash runtime
    """

    defaults = ContextPruningConfig()
    obj = config.get("context_pruning")
    if not isinstance(obj, dict):
        return defaults

    enabled = bool(obj.get("enabled", defaults.enabled))

    min_chars_obj = obj.get("min_chars_to_prune", defaults.min_chars_to_prune)
    if isinstance(min_chars_obj, int) and not isinstance(min_chars_obj, bool):
        min_chars_to_prune = max(0, min_chars_obj)
    else:
        min_chars_to_prune = defaults.min_chars_to_prune

    call_timeout_obj = obj.get("call_timeout_ms", defaults.call_timeout_ms)
    if isinstance(call_timeout_obj, int) and not isinstance(call_timeout_obj, bool):
        call_timeout_ms = max(1, call_timeout_obj)
    else:
        call_timeout_ms = defaults.call_timeout_ms

    # options
    options_obj = obj.get("options")
    options = options_obj if isinstance(options_obj, dict) else {}

    max_prune_ratio_obj = options.get("max_prune_ratio", defaults.max_prune_ratio)
    if isinstance(max_prune_ratio_obj, (int, float)) and not isinstance(max_prune_ratio_obj, bool):
        max_prune_ratio = float(max_prune_ratio_obj)
        if max_prune_ratio < 0.0:
            max_prune_ratio = 0.0
        if max_prune_ratio > 1.0:
            max_prune_ratio = 1.0
    else:
        max_prune_ratio = defaults.max_prune_ratio

    min_keep_lines_obj = options.get("min_keep_lines", defaults.min_keep_lines)
    if isinstance(min_keep_lines_obj, int) and not isinstance(min_keep_lines_obj, bool):
        min_keep_lines = max(0, min_keep_lines_obj)
    else:
        min_keep_lines = defaults.min_keep_lines

    timeout_ms_obj = options.get("timeout_ms", defaults.timeout_ms)
    if isinstance(timeout_ms_obj, int) and not isinstance(timeout_ms_obj, bool):
        timeout_ms = max(1, timeout_ms_obj)
    else:
        timeout_ms = defaults.timeout_ms

    annotate_lines = bool(options.get("annotate_lines", defaults.annotate_lines))
    include_markers = bool(options.get("include_markers", defaults.include_markers))

    return ContextPruningConfig(
        enabled=enabled,
        min_chars_to_prune=min_chars_to_prune,
        call_timeout_ms=call_timeout_ms,
        max_prune_ratio=max_prune_ratio,
        min_keep_lines=min_keep_lines,
        timeout_ms=timeout_ms,
        annotate_lines=annotate_lines,
        include_markers=include_markers,
    )
