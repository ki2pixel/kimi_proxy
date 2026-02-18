"""
Test unitaire pour les routes modèles (JetBrains normalization).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kimi_proxy.api.routes import models as models_routes


def test_openai_models_endpoint_jetbrains_normalization():
    """Test que les IDs de modèles suivent le format JetBrains avec des tirets."""
    # Créer une app test
    app = FastAPI()
    app.include_router(models_routes.router)
    client = TestClient(app)
    
    # Mock la config avec différents formats de clés
    import kimi_proxy.config.loader
    original_get_config = kimi_proxy.config.loader.get_config
    
    def mock_get_config():
        return {
            "models": {
                "nvidia/kimi-k2.5": {
                    "provider": "nvidia",
                    "model": "kimi-for-coding",
                    "max_context_size": 262144
                },
                "managed:kimi-code/kimi-for-coding": {
                    "provider": "managed:kimi-code",
                    "model": "kimi-for-coding",
                    "max_context_size": 262144
                },
                "openrouter/google/codegemma": {
                    "provider": "openrouter",
                    "model": "google/codegemma",
                    "max_context_size": 8192
                }
            }
        }
    
    kimi_proxy.config.loader.get_config = mock_get_config
    
    try:
        # Appeler l'endpoint
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 3
        
        # Vérifier la normalisation
        model_ids = [m["id"] for m in data["data"]]
        
        # vérifier que les slashs sont remplacés
        assert "nvidia-kimi-k2-5" in model_ids
        assert "nvidia/kimi-k2.5" not in model_ids
        
        # vérifier que les points sont remplacés
        assert "managed:kimi-code-kimi-for-coding" in model_ids
        assert "managed:kimi-code/kimi-for-coding" not in model_ids
        
        # vérifier que les deux sont remplacés
        assert "openrouter-google-codegemma" in model_ids
        assert "openrouter/google/codegemma" not in model_ids
        
        # vérifier le cohérence entre id et root
        for model in data["data"]:
            assert model["id"] == model["root"]
            assert model["owned_by"] == "openai"
        
    finally:
        kimi_proxy.config.loader.get_config = original_get_config


def test_model_name_replacement():
    """Test de la fonction de remplacement de caractères pour JetBrains."""
    result = models_routes._sanitize_model_id("nvidia/kimi-k2.5")
    assert result == "nvidia-kimi-k2.5"
    
    result = models_routes._sanitize_model_id("managed:kimi-code/kimi-for-coding")
    assert result == "managed:kimi-code.kimi-for-coding"
    
    result = models_routes._sanitize_model_id("openrouter/google/gemini")
    assert result == "openrouter.google.gemini"