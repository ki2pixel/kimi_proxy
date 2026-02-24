"""
Tests unitaires pour les routes modèles.

Contrat attendu dans ce repo:
- `/api/models` : liste JSON (format dashboard/interne)
- `/models` : format OpenAI-compatible minimal {object:"list", data:[...]}
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kimi_proxy.api.routes import models as models_routes


def test_api_models_returns_list():
    """`/api/models` doit retourner une liste (format dashboard)."""
    app = FastAPI()
    app.include_router(models_routes.router, prefix="/api/models")
    client = TestClient(app)

    import kimi_proxy.api.routes.models
    original_get_config = kimi_proxy.api.routes.models.get_config

    def mock_get_config():
        return {
            "models": {
                "nvidia/kimi-k2.5": {"provider": "nvidia", "model": "kimi-for-coding"},
                "managed:kimi-code/kimi-for-coding": {"provider": "managed:kimi-code", "model": "kimi-for-coding"},
                "openrouter/google/codegemma": {"provider": "openrouter", "model": "google/codegemma"},
            }
        }

    kimi_proxy.api.routes.models.get_config = mock_get_config
    try:
        response = client.get("/api/models")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        assert {"key", "name", "provider", "model"}.issubset(set(data[0].keys()))
    finally:
        kimi_proxy.api.routes.models.get_config = original_get_config


def test_openai_models_returns_object_list():
    """`/models` doit être OpenAI-compatible (object/list/data)."""
    app = FastAPI()
    app.include_router(models_routes.openai_router)
    client = TestClient(app)

    import kimi_proxy.api.routes.models
    original_get_config = kimi_proxy.api.routes.models.get_config

    def mock_get_config():
        return {
            "models": {
                "nvidia/kimi-k2.5": {"provider": "nvidia"},
                "managed:kimi-code/kimi-for-coding": {"provider": "managed:kimi-code"},
            }
        }

    kimi_proxy.api.routes.models.get_config = mock_get_config
    try:
        response = client.get("/models")
        assert response.status_code == 200

        data = response.json()
        assert data.get("object") == "list"
        assert isinstance(data.get("data"), list)
        assert {"id", "object", "created", "owned_by"}.issubset(set(data["data"][0].keys()))
    finally:
        kimi_proxy.api.routes.models.get_config = original_get_config