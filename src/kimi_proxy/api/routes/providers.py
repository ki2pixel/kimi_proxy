"""
Routes API pour la gestion des providers.
"""
from fastapi import APIRouter

from ...config.loader import get_config
from ...config.display import (
    get_provider_display_name,
    get_provider_icon,
    get_provider_color,
    get_model_display_name,
)
from ...core.constants import DEFAULT_MAX_CONTEXT

router = APIRouter()


@router.get("")
async def api_get_providers():
    """Retourne tous les providers avec leurs modèles groupés."""
    config = get_config()
    providers_config = config.get("providers", {})
    models_config = config.get("models", {})
    
    result = []
    for key, provider in providers_config.items():
        safe_provider = {
            "key": key,
            "type": provider.get("type", "openai"),
            "name": get_provider_display_name(key),
            "has_api_key": bool(provider.get("api_key")),
            "icon": get_provider_icon(key),
            "color": get_provider_color(key),
            "models": []
        }
        
        for model_key, model in models_config.items():
            if model.get("provider") == key:
                safe_provider["models"].append({
                    "key": model_key,
                    "model": model.get("model"),
                    "name": get_model_display_name(model_key),
                    "max_context_size": model.get("max_context_size", DEFAULT_MAX_CONTEXT),
                    "capabilities": model.get("capabilities", [])
                })
        
        # Trie les modèles par nom
        safe_provider["models"].sort(key=lambda x: x["name"])
        result.append(safe_provider)
    
    # Trie les providers: Kimi d'abord, puis alphabétique
    result.sort(key=lambda x: (0 if "kimi" in x["key"] else 1, x["name"]))
    
    return result
