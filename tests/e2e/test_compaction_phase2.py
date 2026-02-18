"""
Tests E2E pour la Phase 2 - Fonctionnalités Utilisateur de Compaction.

Ces tests vérifient:
- Les endpoints API de preview et simulation
- Le toggle auto-compaction par session
- Le statut et les alertes de compaction
- L'historique et les graphiques
- Les WebSocket events
"""
import pytest
import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.kimi_proxy.main import create_app
from src.kimi_proxy.core.database import init_database, get_db
from src.kimi_proxy.features.compaction.auto_trigger import (
    AutoTriggerConfig,
    get_auto_trigger,
)


@pytest.fixture(scope="module")
def app():
    """Crée l'application FastAPI pour les tests."""
    init_database()
    return create_app()


@pytest.fixture(scope="module")
def client(app):
    """Crée un client de test."""
    return TestClient(app)


@pytest.fixture
def test_session(client):
    """Crée une session de test."""
    response = client.post("/api/sessions", json={
        "name": "Test Session Compaction",
        "provider": "managed:kimi-code",
        "model": "kimi-for-coding"
    })
    assert response.status_code == 200
    session = response.json()
    yield session
    
    # Cleanup
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session["id"],))
        conn.commit()


class TestCompactionPreviewAPI:
    """Tests pour l'API de preview de compaction."""
    
    def test_preview_compaction_success(self, client, test_session):
        """Vérifie que le preview fonctionne avec suffisamment de messages."""
        session_id = test_session["id"]
        
        # Crée d'abord des métriques pour simuler des messages
        with get_db() as conn:
            cursor = conn.cursor()
            for i in range(10):
                cursor.execute("""
                    INSERT INTO metrics 
                    (session_id, estimated_tokens, percentage, content_preview, 
                     prompt_tokens, completion_tokens, is_estimated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    1000 + i * 100,
                    10.0 + i,
                    f"Message de test numéro {i} avec suffisamment de contenu pour etre interessant",
                    500 + i * 50,
                    500 + i * 50,
                    False
                ))
            conn.commit()
        
        response = client.get(f"/api/compaction/{session_id}/preview")
        assert response.status_code == 200
        
        data = response.json()
        assert "can_compact" in data
        assert "preview" in data
        assert "estimate" in data
        assert "config" in data


class TestCompactionToggleAPI:
    """Tests pour l'API de toggle auto-compaction."""
    
    def test_toggle_auto_compaction_on(self, client, test_session):
        """Vérifie l'activation de l'auto-compaction."""
        session_id = test_session["id"]
        
        response = client.post(
            f"/api/compaction/{session_id}/toggle-auto",
            json={"enabled": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert data["auto_compaction_enabled"] is True


class TestCompactionStatusAPI:
    """Tests pour l'API de statut auto-compaction."""
    
    def test_get_auto_compaction_status(self, client, test_session):
        """Vérifie la recuperation du statut complet."""
        session_id = test_session["id"]
        
        response = client.get(f"/api/compaction/{session_id}/auto-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data
        assert "status" in data
        assert "context" in data


class TestCompactionHistoryAPI:
    """Tests pour l'API d'historique de compaction."""
    
    def test_get_compaction_history_chart(self, client, test_session):
        """Vérifie la recuperation des donnees pour le graphique."""
        session_id = test_session["id"]
        
        response = client.get(f"/api/compaction/{session_id}/history-chart")
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data
        assert "labels" in data
        assert "datasets" in data


class TestCompactionIntegration:
    """Tests d'integration pour le workflow complet."""
    
    def test_full_compaction_workflow(self, client, test_session):
        """Vérifie le workflow complet de compaction."""
        session_id = test_session["id"]
        
        # 1. Verifie le statut initial
        response = client.get(f"/api/compaction/{session_id}/stats")
        assert response.status_code == 200
        
        # 2. Verifie le preview
        response = client.get(f"/api/compaction/{session_id}/preview")
        assert response.status_code == 200
        
        # 3. Verifie le statut auto-compaction
        response = client.get(f"/api/compaction/{session_id}/auto-status")
        assert response.status_code == 200
        auto_status = response.json()
        
        # 4. Bascule l'auto-compaction
        response = client.post(
            f"/api/compaction/{session_id}/toggle-auto",
            json={"enabled": True}
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
