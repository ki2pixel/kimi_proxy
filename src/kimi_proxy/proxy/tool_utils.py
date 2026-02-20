"""
Utilitaires pour les tool calls dans le proxy.
Pourquoi: Générer et valider les IDs de tool calls selon les spécifications des providers.
"""
import re
import string
import secrets
from typing import Dict, Any, List, Optional


def generate_tool_call_id(length: int = 9) -> str:
    """
    Génère un ID de tool call alphanumérique valide.
    
    Args:
        length: Longueur de l'ID (défaut: 9 pour NVIDIA)
        
    Returns:
        ID alphanumérique de la longueur spécifiée
        
    Raises:
        ValueError: Si length < 1
    """
    if length < 1:
        raise ValueError("Length must be at least 1")
    
    # Caractères autorisés: a-z, A-Z, 0-9
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def validate_tool_call_id(tool_id: str) -> bool:
    """
    Valide qu'un ID de tool call respecte le format requis.
    
    Args:
        tool_id: ID à valider
        
    Returns:
        True si valide, False sinon
    """
    # Format requis: a-z, A-Z, 0-9, longueur 9
    pattern = r'^[a-zA-Z0-9]{9}$'
    return bool(re.match(pattern, tool_id))


def fix_tool_calls_in_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Corrige les tool calls dans une requête en générant les IDs manquants.
    
    Args:
        body: Corps de la requête JSON
        
    Returns:
        Corps modifié avec les IDs de tool calls valides
    """
    if not isinstance(body, dict):
        return body
    
    # Traite les tool calls dans les messages
    messages = body.get('messages', [])
    for message in messages:
        if not isinstance(message, dict):
            continue
            
        # Vérifie les tool calls dans le message
        tool_calls = message.get('tool_calls', [])
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                    
                tool_call_id = tool_call.get('id')
                if not tool_call_id or not validate_tool_call_id(tool_call_id):
                    # Génère un nouvel ID valide
                    new_id = generate_tool_call_id()
                    tool_call['id'] = new_id
                    print(f"🔧 [TOOL CALL] ID généré: {new_id}")
    
    return body


def validate_and_fix_tool_calls(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valide et corrige tous les tool calls et tool results dans la requête.
    
    Args:
        body: Corps de la requête
        
    Returns:
        Corps corrigé et statistiques des modifications
    """
    stats = {
        "total_tool_calls": 0,
        "total_tool_results": 0,
        "fixed_ids": 0,
        "invalid_ids": []
    }
    
    if not isinstance(body, dict):
        return body, stats
    
    messages = body.get('messages', [])
    for message in messages:
        if not isinstance(message, dict):
            continue
            
        # Traite les tool calls dans les messages assistant
        tool_calls = message.get('tool_calls', [])
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                    
                stats["total_tool_calls"] += 1
                tool_call_id = tool_call.get('id')
                
                if not tool_call_id:
                    stats["fixed_ids"] += 1
                    new_id = generate_tool_call_id()
                    tool_call['id'] = new_id
                    print(f"🔧 [TOOL CALL] ID manquant généré: {new_id}")
                elif not validate_tool_call_id(tool_call_id):
                    stats["invalid_ids"].append(tool_call_id)
                    stats["fixed_ids"] += 1
                    new_id = generate_tool_call_id()
                    tool_call['id'] = new_id
                    print(f"🔧 [TOOL CALL] ID invalide '{tool_call_id}' remplacé par: {new_id}")
        
        # Traite les tool_result_id dans les messages tool/assistant
        tool_result_id = message.get('tool_call_id')
        if tool_result_id is not None:  # Inclut les chaînes vides
            stats["total_tool_results"] += 1
            if not tool_result_id or not validate_tool_call_id(tool_result_id):
                stats["fixed_ids"] += 1
                new_id = generate_tool_call_id()
                message['tool_call_id'] = new_id
                print(f"🔧 [TOOL RESULT] tool_call_id invalide '{tool_result_id}' remplacé par: {new_id}")
    
    return body, stats
