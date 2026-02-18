"""
Configuration des tests pytest.
"""
import pytest
import sys
import os
import asyncio

# Ajoute src au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# Configuration pytest-asyncio
def pytest_configure(config):
    """Configure pytest pour async."""
    config.addinivalue_line(
        "markers", "asyncio: marque un test comme asynchrone"
    )


@pytest.fixture
def event_loop():
    """Crée un event loop pour les tests async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
