"""
Tests de régression E2E pour Kimi Proxy Dashboard.
"""
import pytest
import httpx
import asyncio
import websockets
import json

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test que le health check fonctionne."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_list_providers():
    """Test que la liste des providers fonctionne."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_models():
    """Test que la liste des modèles fonctionne."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_session():
    """Test la création de session."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/sessions",
            json={"name": "Test Session", "provider": "managed:kimi-code"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Session"


@pytest.mark.asyncio
async def test_get_active_session():
    """Test la récupération de la session active."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/sessions/active")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_openai_models_endpoint():
    """Test l'endpoint OpenAI-compatible /models."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/models")
        assert response.status_code == 200
        data = response.json()
        assert "object" in data
        assert data["object"] == "list"
        assert "data" in data


@pytest.mark.asyncio
async def test_websocket_connection():
    """Test la connexion WebSocket."""
    try:
        async with websockets.connect(WS_URL) as websocket:
            # Attend le message d'init
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            data = json.loads(response)
            assert "type" in data
    except (websockets.exceptions.ConnectionRefused, asyncio.TimeoutError):
        pytest.skip("Serveur non disponible pour test WebSocket")


@pytest.mark.asyncio
async def test_sanitizer_stats():
    """Test l'endpoint de stats sanitizer."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/sanitizer/stats")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "stats" in data


@pytest.mark.asyncio
async def test_memory_stats():
    """Test l'endpoint de stats mémoire."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/memory/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_memory_tokens" in data


@pytest.mark.asyncio
async def test_rate_limit_status():
    """Test l'endpoint de rate limit."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/rate-limit")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "current_rpm" in data
