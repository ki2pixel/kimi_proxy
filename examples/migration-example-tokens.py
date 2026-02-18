# =============================================================================
# EXEMPLE DE MIGRATION: Module core/tokens.py
# =============================================================================
# Ce fichier montre comment extraire le code de main.py vers un module dédié
# =============================================================================

# ------------------------------------------------------------------------------
# AVANT (dans main.py - lignes dispersées)
# ------------------------------------------------------------------------------

# En haut de main.py:
# import tiktoken
# ENCODING = tiktoken.get_encoding("cl100k_base")

# Quelque part dans main.py:
# def count_tokens_tiktoken(messages: list) -> int:
#     if not messages:
#         return 0
#     token_count = 0
#     for message in messages:
#         token_count += 3
#         ...

# ------------------------------------------------------------------------------
# APRÈS (src/kimi_proxy/core/tokens.py)
# ------------------------------------------------------------------------------

"""
Module de tokenization pour Kimi Proxy Dashboard.

Utilise Tiktoken (cl100k_base) pour un comptage précis des tokens
compatible avec OpenAI, Kimi, et autres providers.
"""

import tiktoken
from typing import List, Dict, Union, Optional

# Encoding partagé (cl100k_base = encodage GPT-4/Claude/Kimi)
ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens_tiktoken(messages: List[dict]) -> int:
    """
    Compte précisément les tokens d'une liste de messages.
    
    Format compatible OpenAI/Kimi:
    - +3 tokens par message (délimiteurs)
    - +1 token par rôle
    - Contenu encodé avec cl100k_base
    - +3 tokens de fin
    
    Args:
        messages: Liste de messages au format OpenAI
                 [{"role": "user", "content": "..."}, ...]
    
    Returns:
        Nombre total de tokens
    
    Example:
        >>> messages = [{"role": "user", "content": "Hello"}]
        >>> count_tokens_tiktoken(messages)
        7
    """
    if not messages:
        return 0
    
    token_count = 3  # Tokens de prime abord
    
    for message in messages:
        token_count += 3  # start/role/end tokens
        
        role = message.get("role", "")
        content = message.get("content", "")
        
        token_count += len(ENCODING.encode(role))
        
        if isinstance(content, str):
            token_count += len(ENCODING.encode(content))
        elif isinstance(content, list):
            # Format multimodal (GPT-4V, etc.)
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text = part.get("text", "")
                        token_count += len(ENCODING.encode(text))
                    elif part.get("type") == "image_url":
                        token_count += 512  # Estimation image
    
    token_count += 3  # Tokens de fin
    return token_count


def count_tokens_text(text: str) -> int:
    """
    Compte les tokens d'un texte simple.
    
    Args:
        text: Texte à compter
    
    Returns:
        Nombre de tokens
    
    Example:
        >>> count_tokens_text("Hello world")
        2
    """
    if not text:
        return 0
    return len(ENCODING.encode(text))


def count_message_tokens(message: dict) -> Dict[str, int]:
    """
    Compte détaillé des tokens d'un seul message.
    
    Returns:
        Dict avec décomposition: {role_tokens, content_tokens, total}
    """
    role = message.get("role", "")
    content = message.get("content", "")
    
    role_tokens = len(ENCODING.encode(role))
    
    if isinstance(content, str):
        content_tokens = len(ENCODING.encode(content))
    else:
        content_tokens = count_tokens_tiktoken([message]) - 3 - role_tokens
    
    return {
        "role_tokens": role_tokens,
        "content_tokens": content_tokens,
        "overhead": 3,  # Délimiteurs
        "total": 3 + role_tokens + content_tokens
    }


def estimate_tokens_for_model(
    text: str, 
    model: str = "gpt-4"
) -> int:
    """
    Estimation des tokens pour un modèle spécifique.
    
    Certains modèles utilisent des encodages différents.
    
    Args:
        text: Texte à estimer
        model: Nom du modèle (pour futur support multi-encoding)
    
    Returns:
        Estimation du nombre de tokens
    """
    # Pour l'instant, tous les modèles supportés utilisent cl100k_base
    # Futur: support pour p50k_base, r50k_base, etc.
    return count_tokens_text(text)


# =============================================================================
# TESTS UNITAIRES (tests/unit/test_tokens.py)
# =============================================================================

"""
# tests/unit/test_tokens.py
import pytest
from kimi_proxy.core.tokens import (
    count_tokens_tiktoken,
    count_tokens_text,
    count_message_tokens
)

class TestTokenization:
    def test_count_tokens_empty(self):
        assert count_tokens_tiktoken([]) == 0
    
    def test_count_tokens_simple(self):
        messages = [{"role": "user", "content": "Hello"}]
        tokens = count_tokens_tiktoken(messages)
        assert tokens > 0  # role + content + overhead
    
    def test_count_tokens_text(self):
        assert count_tokens_text("") == 0
        assert count_tokens_text("Hello") == 1
        assert count_tokens_text("Hello world") == 2
    
    def test_count_message_detailed(self):
        message = {"role": "user", "content": "Test"}
        result = count_message_tokens(message)
        assert "role_tokens" in result
        assert "content_tokens" in result
        assert result["total"] == 3 + result["role_tokens"] + result["content_tokens"]
"""


# =============================================================================
# UTILISATION DANS L'APPLICATION
# =============================================================================

"""
# Dans src/kimi_proxy/features/sanitizer/masking.py
from ...core.tokens import count_tokens_text

class ContentMasker:
    def should_mask(self, content: str, threshold: int = 1000) -> bool:
        return count_tokens_text(content) > threshold


# Dans src/kimi_proxy/api/routes/proxy.py
from ...core.tokens import count_tokens_tiktoken

@router.post("/chat/completions")
async def proxy_chat(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    token_count = count_tokens_tiktoken(messages)
    # ... suite du traitement
"""
