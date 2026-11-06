"""
Configuration des tests pytest.
"""
import pytest
import sys
import os

# Ajoute src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture
def test_config():
    """Fixture pour la configuration de test."""
    return {
        "providers": {
            "test": {
                "type": "openai",
                "base_url": "http://localhost:9999",
                "api_key": "test-key"
            }
        },
        "models": {
            "test/model": {
                "provider": "test",
                "model": "test-model",
                "max_context_size": 32768
            }
        }
    }


@pytest.fixture
def sample_messages():
    """Fixture pour des messages de test."""
    return [
        {"role": "system", "content": "Tu es un assistant utile."},
        {"role": "user", "content": "Bonjour, comment ça va?"},
        {"role": "assistant", "content": "Je vais bien, merci!"}
    ]
