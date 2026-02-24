"""Tests de régression E2E pour Kimi Proxy Dashboard.

Objectif: ces tests doivent être auto-contenus (ne pas dépendre d'un serveur
déjà lancé sur localhost:8000). On teste donc l'app ASGI directement via
FastAPI TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from kimi_proxy.main import create_app
from kimi_proxy.core.database import init_database


@pytest.fixture(scope="module")
def app():
    init_database()
    return create_app()


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


def test_health_endpoint(client: TestClient):
    """Test que le health check fonctionne."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") in {"ok", "opérationnel"}


def test_list_providers(client: TestClient):
    """Test que la liste des providers fonctionne."""
    response = client.get("/api/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_models(client: TestClient):
    """Test que la liste des modèles fonctionne (format dashboard: liste)."""
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_session(client: TestClient):
    """Test la création de session."""
    response = client.post(
        "/api/sessions",
        json={"name": "Test Session", "provider": "managed:kimi-code"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test Session"


def test_get_active_session(client: TestClient):
    """Test la récupération de la session active."""
    response = client.get("/api/sessions/active")
    assert response.status_code == 200


def test_openai_models_endpoint(client: TestClient):
    """Test l'endpoint OpenAI-compatible /models."""
    response = client.get("/models")
    assert response.status_code == 200
    data = response.json()
    assert data.get("object") == "list"
    assert isinstance(data.get("data"), list)


def test_websocket_connection(client: TestClient):
    """Test la connexion WebSocket (ASGI in-process)."""
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_json()
        assert isinstance(data, dict)
        assert "type" in data


def test_sanitizer_stats(client: TestClient):
    """Test l'endpoint de stats sanitizer."""
    response = client.get("/api/sanitizer/stats")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "stats" in data


def test_memory_stats(client: TestClient):
    """Test l'endpoint de stats mémoire."""
    response = client.get("/api/memory/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_memory_tokens" in data


def test_rate_limit_status(client: TestClient):
    """Test l'endpoint de rate limit."""
    response = client.get("/api/rate-limit")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "current_rpm" in data
