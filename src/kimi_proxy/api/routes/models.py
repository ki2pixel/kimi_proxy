"""
Routes API pour la liste des modèles.
"""
from fastapi import APIRouter
from typing import Dict, Any
import logging

from ...config.loader import get_config
from ...config.display import get_model_display_name
from ...core.constants import DEFAULT_MAX_CONTEXT

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def openai_models():
    """
    Endpoint OpenAI-compatible GET /models.
    
    Retourne les IDs originaux des modèles sans préfixe.
    Structure: {"object": "list", "data": [model1, model2, ...]}
    """
    config = get_config()
    models_config = config.get("models", {})
    
    models_list = []
    for model_key, model_data in models_config.items():
        models_list.append({
            "id": model_key,
            "object": "model",
            "created": 1704067200,
            "owned_by": model_data.get("provider", "unknown")
        })
    
    return {
        "object": "list",
        "data": models_list
    }


@router.get("/all")
async def api_get_models():
    """
    Retourne tous les modèles disponibles depuis la config (format détaillé interne).
    
    Cet endpoint est utilisé par le dashboard web pour l'affichage détaillé.
    """
    config = get_config()
    models_config = config.get("models", {})
    
    result = []
    for model_key, model in models_config.items():
        result.append({
            "key": model_key,
            "model": model.get("model"),
            "name": get_model_display_name(model_key),
            "provider": model.get("provider"),
            "max_context_size": model.get("max_context_size", DEFAULT_MAX_CONTEXT),
            "capabilities": model.get("capabilities", [])
        })
    
    # Trie par provider puis par nom
    result.sort(key=lambda x: (x.get("provider", ""), x.get("name", "")))
    
    return result