"""
Tests unitaires pour le client proxy HTTPX.

Pourquoi: le client gère les timeouts, retries et connexions.
Ces tests vérifient la robustesse réseau.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from kimi_proxy.proxy.client import (
    ProxyClient,
    create_proxy_client,
    PROVIDER_TIMEOUTS
)


class TestProviderTimeouts:
    """Tests des timeouts par provider."""
    
    def test_all_providers_have_timeouts(self):
        """Tous les providers supportés ont un timeout défini."""
        providers = ["gemini", "kimi", "nvidia", "mistral", "openrouter", 
                     "siliconflow", "groq", "cerebras"]
        for provider in providers:
            assert provider in PROVIDER_TIMEOUTS
            assert PROVIDER_TIMEOUTS[provider] > 0
    
    def test_default_timeout_exists(self):
        """Un timeout par défaut existe."""
        assert "default" in PROVIDER_TIMEOUTS


class TestProxyClient:
    """Tests du client proxy."""
    
    def test_init_default_values(self):
        """Initialisation avec valeurs par défaut."""
        client = ProxyClient()
        assert client.timeout == 120.0
        assert client.max_retries == 2
        assert client.retry_delay == 1.0
    
    def test_init_custom_values(self):
        """Initialisation avec valeurs custom."""
        client = ProxyClient(timeout=60.0, max_retries=3, retry_delay=2.0)
        assert client.timeout == 60.0
        assert client.max_retries == 3
        assert client.retry_delay == 2.0
    
    def test_build_request(self):
        """Construction de requête."""
        client = ProxyClient()
        req = client.build_request(
            "POST",
            "https://api.example.com/chat",
            {"Content-Type": "application/json"},
            '{"messages": []}'
        )
        
        assert req.method == "POST"
        assert str(req.url) == "https://api.example.com/chat"
        assert req.headers["Content-Type"] == "application/json"


class TestCreateProxyClient:
    """Tests de la factory."""
    
    def test_factory_default(self):
        """Factory crée un client avec valeurs par défaut."""
        client = create_proxy_client()
        assert isinstance(client, ProxyClient)
        assert client.timeout == 120.0
    
    def test_factory_custom(self):
        """Factory accepte des paramètres custom."""
        client = create_proxy_client(timeout=90.0, max_retries=1)
        assert client.timeout == 90.0
        assert client.max_retries == 1
