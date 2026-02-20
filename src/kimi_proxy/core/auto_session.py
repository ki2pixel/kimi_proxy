"""
Module d'auto-création de sessions.

Pourquoi: Détecte automatiquement lorsqu'une requête provient d'un provider
différent de la session active et crée une nouvelle session automatiquement.
"""
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from ..core.database import create_session, get_active_session
from ..config.loader import get_config


# Cache pour le statut auto-session par session
_auto_session_cache: Dict[int, bool] = {}


def get_auto_session_status(session_id: int) -> bool:
    """
    Récupère le statut de l'auto-session pour une session donnée.
    
    Args:
        session_id: ID de la session
        
    Returns:
        True si l'auto-session est activée, False sinon
    """
    return _auto_session_cache.get(session_id, True)  # Par défaut activé


def set_auto_session_status(session_id: int, enabled: bool) -> None:
    """
    Définit le statut de l'auto-session pour une session donnée.
    
    Args:
        session_id: ID de la session
        enabled: True pour activer, False pour désactiver
    """
    _auto_session_cache[session_id] = enabled


def detect_provider_from_model(model: str, models_config: Dict[str, Any]) -> Optional[str]:
    """
    Détecte le provider à partir du nom du modèle.
    
    Args:
        model: Nom du modèle (ex: "nvidia/kimi-k2.5" ou "kimi-for-coding")
        models_config: Configuration des modèles depuis config.toml
        
    Returns:
        Clé du provider ou None si non trouvé
    """
    # 1. Vérifier si c'est une clé exacte dans models
    if model in models_config:
        return models_config[model].get("provider")
    
    # 2. Vérifier avec le préfixe (ex: "kimi-code/kimi-for-coding")
    for model_key, model_data in models_config.items():
        if model_key.endswith(f"/{model}") or model_key == model:
            return model_data.get("provider")
    
    # 3. Recherche par nom de modèle interne
    for model_key, model_data in models_config.items():
        internal_model = model_data.get("model", "")
        if internal_model == model or internal_model.endswith(f"/{model}"):
            return model_data.get("provider")
    
    return None


def should_auto_create_session(
    detected_provider: str,
    current_session: Optional[Dict[str, Any]]
) -> bool:
    """
    Détermine si une nouvelle session doit être créée automatiquement.
    
    Args:
        detected_provider: Provider détecté depuis la requête
        current_session: Session active actuelle
        
    Returns:
        True si une nouvelle session doit être créée
    """
    if not current_session:
        return True  # Pas de session active, créer une nouvelle
    
    current_provider = current_session.get("provider", "managed:kimi-code")
    
    # Si les providers sont différents, créer une nouvelle session
    if detected_provider != current_provider:
        return True
    
    return False


def auto_create_session(
    detected_provider: str,
    detected_model: str,
    models_config: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Crée automatiquement une nouvelle session pour un provider donné.
    
    Args:
        detected_provider: Provider détecté
        detected_model: Modèle détecté
        models_config: Configuration des modèles
        
    Returns:
        Nouvelle session créée ou None en cas d'erreur
    """
    try:
        # Générer un nom de session basé sur le provider et l'heure
        timestamp = datetime.now().strftime("%H:%M:%S")
        provider_name = detected_provider.replace("managed:", "").replace("-", " ").title()
        session_name = f"Session {provider_name} {timestamp}"
        
        # Créer la session
        new_session = create_session(
            name=session_name,
            provider=detected_provider,
            model=detected_model
        )
        
        print(f"🔄 [AUTO SESSION] Nouvelle session créée: #{new_session['id']} "
              f"({detected_provider}/{detected_model})")
        
        return new_session
        
    except Exception as e:
        print(f"⚠️ [AUTO SESSION] Erreur création session: {e}")
        return None


def process_auto_session(
    request_body: Dict[str, Any],
    current_session: Optional[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """
    Traite la logique d'auto-session pour une requête entrante.
    
    Args:
        request_body: Body de la requête (parsé en JSON)
        current_session: Session active actuelle
        
    Returns:
        Tuple (session à utiliser, booléen indiquant si une nouvelle session a été créée)
    """
    config = get_config()
    models_config = config.get("models", {})
    
    # Extraire le modèle de la requête
    model = request_body.get("model", "")
    if not model:
        return current_session, False
    
    # Détecter le provider depuis le modèle
    detected_provider = detect_provider_from_model(model, models_config)
    if not detected_provider:
        return current_session, False
    
    # Mapper le modèle pour le provider détecté
    from ..proxy.router import map_model_name
    mapped_model = map_model_name(model, models_config)
    
    # Vérifier si on doit créer une nouvelle session
    if not should_auto_create_session(detected_provider, current_session):
        return current_session, False
    
    # Vérifier si l'auto-session est activée pour cette session
    if current_session:
        session_id = current_session.get("id", 0)
        if not get_auto_session_status(session_id):
            return current_session, False  # Mode auto désactivé
    
    # Créer la nouvelle session avec le modèle mappé
    new_session = auto_create_session(detected_provider, mapped_model, models_config)
    if new_session:
        return new_session, True
    
    return current_session, False
