"""
Tests unitaires pour le module de tokenization.
"""
import pytest

from kimi_proxy.core.tokens import count_tokens_text, count_tokens_tiktoken


def test_count_tokens_text_empty():
    """Test avec texte vide."""
    assert count_tokens_text("") == 0


def test_count_tokens_text_simple():
    """Test avec texte simple."""
    tokens = count_tokens_text("Bonjour le monde")
    assert tokens > 0


def test_count_tokens_tiktoken_empty():
    """Test avec liste vide."""
    assert count_tokens_tiktoken([]) == 0


def test_count_tokens_tiktoken_messages(sample_messages):
    """Test avec messages."""
    tokens = count_tokens_tiktoken(sample_messages)
    assert tokens > 0
    # Chaque message ajoute au moins 3 tokens (début/role/fin)
    assert tokens >= len(sample_messages) * 3
