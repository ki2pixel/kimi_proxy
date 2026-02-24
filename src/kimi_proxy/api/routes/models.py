"""Routes API pour la liste des modèles.

Convention dans ce repo:
- `/api/models` : format interne (liste) utilisé par le dashboard.
- `/models` : endpoint OpenAI-compatible minimal (object/list/data).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

from ...config.display import get_model_display_name
from ...config.loader import get_config
from ...core.constants import DEFAULT_MAX_CONTEXT

logger = logging.getLogger(__name__)

# Router dashboard (monté sous /api/models)
router = APIRouter()

# Router OpenAI-compatible (monté à la racine)
openai_router = APIRouter()


def _build_internal_models_list(models_config: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for model_key, model in models_config.items():
        result.append(
            {
                "key": model_key,
                "model": model.get("model"),
                "name": get_model_display_name(model_key),
                "provider": model.get("provider"),
                "max_context_size": model.get("max_context_size", DEFAULT_MAX_CONTEXT),
                "capabilities": model.get("capabilities", []),
            }
        )

    # Trie par provider puis par nom
    result.sort(key=lambda x: (x.get("provider", ""), x.get("name", "")))
    return result


def _build_openai_models_list(models_config: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    models_list: List[Dict[str, Any]] = []
    for model_key, model_data in models_config.items():
        models_list.append(
            {
                "id": model_key,
                "object": "model",
                # Valeur stable (placeholder) - OpenAI renvoie un timestamp "created"
                "created": 1704067200,
                # Compat OpenAI clients: owned_by string
                "owned_by": "openai",
            }
        )
    return models_list


@router.get("")
async def api_get_models() -> List[Dict[str, Any]]:
    """Retourne les modèles disponibles (format interne liste) pour le dashboard."""
    config = get_config()
    models_config = config.get("models", {})
    return _build_internal_models_list(models_config)


@router.get("/all")
async def api_get_models_all() -> List[Dict[str, Any]]:
    """Alias rétro-compatible: `/api/models/all` (même payload que `/api/models`)."""
    return await api_get_models()


@openai_router.get("/models")
async def openai_models() -> Dict[str, Any]:
    """Endpoint OpenAI-compatible minimal: GET /models."""
    config = get_config()
    models_config = config.get("models", {})
    return {
        "object": "list",
        "data": _build_openai_models_list(models_config),
    }