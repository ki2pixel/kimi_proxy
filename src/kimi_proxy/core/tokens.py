"""
Tokenization avec Tiktoken - Comptage précis des tokens.
"""
import json
from typing import List, Union

import tiktoken

from .exceptions import TokenizationError

# Encodage Tiktoken (cl100k_base = même encodage que GPT-4, Kimi, etc.)
ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens_tiktoken(messages: List[dict]) -> int:
    """
    Compte précisément les tokens d'une liste de messages.
    Format compatible OpenAI/Kimi.
    
    Args:
        messages: Liste de messages au format OpenAI
        
    Returns:
        Nombre de tokens estimé
        
    Raises:
        TokenizationError: Si une erreur survient lors du comptage
    """
    if not messages:
        return 0
    
    try:
        token_count = 0
        
        for message in messages:
            token_count += 3  # Tokens de début/role/fin
            role = message.get("role", "")
            content = message.get("content", "")
            
            token_count += len(ENCODING.encode(role))
            
            if isinstance(content, str):
                token_count += len(ENCODING.encode(content))
            elif isinstance(content, list):
                # Format multimodal (images, etc.)
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            text = part.get("text", "")
                            token_count += len(ENCODING.encode(text))
                        elif part.get("type") == "image_url":
                            # Estimation: ~512 tokens par image
                            token_count += 512
        
        token_count += 3  # Tokens de fin
        return token_count
    except Exception as e:
        raise TokenizationError(
            message=f"Erreur lors du comptage des tokens: {e}",
            content_preview=str(messages)[:200] if messages else None
        )


def count_tokens_text(text: str) -> int:
    """
    Compte les tokens d'un texte simple.
    
    Args:
        text: Texte à analyser
        
    Returns:
        Nombre de tokens
    """
    if not text:
        return 0
    return len(ENCODING.encode(text))


def count_tokens_from_string(content: str) -> int:
    """
    Alias de count_tokens_text pour compatibilité.
    """
    return count_tokens_text(content)


def estimate_tokens_json(data: Union[dict, list]) -> int:
    """
    Estime les tokens d'une structure JSON.
    
    Args:
        data: Données JSON (dict ou list)
        
    Returns:
        Nombre de tokens estimé
    """
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        return count_tokens_text(json_str)
    except (TypeError, ValueError):
        return 0
