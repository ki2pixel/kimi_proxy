"""
Routing des requêtes vers les providers.
"""
from typing import Dict, Any, Optional
import logging

from ..core.constants import DEFAULT_MAX_CONTEXT, DEFAULT_PROVIDER

logger = logging.getLogger(__name__)


def get_target_url_for_session(
    session: dict,
    providers: Dict[str, Dict[str, Any]]
) -> str:
    """
    Récupère l'URL cible pour la session en fonction du provider.
    
    Args:
        session: Session active
        providers: Dictionnaire des providers configurés
        
    Returns:
        URL cible pour les appels API
    """
    if not session:
        return "https://api.kimi.com/coding/v1"
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    provider = providers.get(provider_key, {})
    base_url = provider.get("base_url", "")
    
    # Protection contre la boucle infinie
    if base_url and "127.0.0.1:8000" not in base_url and "localhost:8000" not in base_url:
        return base_url.rstrip("/")
    
    return "https://api.kimi.com/coding/v1"


def get_provider_host_header(target_url: str) -> Optional[str]:
    """
    Extrait le header Host approprié pour l'URL cible.
    
    Args:
        target_url: URL cible
        
    Returns:
        Header Host ou None
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(target_url)
        return parsed.netloc
    except Exception:
        return None


def find_heavy_duty_model(
    provider_key: str,
    current_model: str,
    required_context: int,
    models: Dict[str, Dict[str, Any]]
) -> Optional[str]:
    """
    Trouve un modèle avec plus de contexte dans le même provider.
    
    Args:
        provider_key: Clé du provider
        current_model: Modèle actuel
        required_context: Contexte minimum requis
        models: Dictionnaire des modèles
        
    Returns:
        Clé du modèle fallback ou None
    """
    current_model_data = models.get(current_model, {})
    current_context = current_model_data.get("max_context_size", DEFAULT_MAX_CONTEXT)
    
    candidates = []
    for model_key, model_data in models.items():
        if model_data.get("provider") == provider_key:
            model_context = model_data.get("max_context_size", DEFAULT_MAX_CONTEXT)
            if model_context > current_context and model_context >= required_context:
                candidates.append((model_key, model_context))
    
    if not candidates:
        return None
    
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


def get_max_context_for_session(
    session: dict,
    models: Dict[str, Dict[str, Any]],
    default: int = DEFAULT_MAX_CONTEXT
) -> int:
    """
    Récupère le contexte max pour une session.
    
    Args:
        session: Session active
        models: Dictionnaire des modèles
        default: Valeur par défaut
        
    Returns:
        Taille de contexte maximale
    """
    if not session:
        return default
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    model_key = session.get("model")
    
    # Si un modèle spécifique est stocké, utilise son contexte
    if model_key and model_key in models:
        return models[model_key].get("max_context_size", default)
    
    # Sinon, trouve le contexte le plus petit parmi les modèles du provider
    min_context = None
    for mk, model in models.items():
        if model.get("provider") == provider_key:
            ctx = model.get("max_context_size", default)
            if min_context is None or ctx < min_context:
                min_context = ctx
    
    return min_context if min_context else default


def map_model_name(
    client_model: str,
    models: Dict[str, Dict[str, Any]]
) -> str:
    """
    Mappe le nom du modèle client vers le nom provider.
    
    Args:
        client_model: Nom du modèle envoyé par le client
        models: Dictionnaire des modèles configurés
        
    Returns:
        Nom du modèle pour l'API provider
    """
    logger.debug(f"Mapping model: client_model='{client_model}'")
    
    # 1. Vérifier d'abord si c'est une clé exacte
    if client_model in models:
        logger.debug(f"Clé exacte trouvée: {client_model}")
        return models[client_model].get("model", client_model)
    
    # 2. Sinon, split sur le slash pour retourner le suffixe
    if "/" in client_model:
        fallback = client_model.split("/", 1)[1]
        logger.debug(f"Fallback provider split: {client_model} → {fallback}")
        return fallback
    
    logger.warning(f"Aucun mapping trouvé pour '{client_model}', fallback vers '{client_model}'")
    return client_model