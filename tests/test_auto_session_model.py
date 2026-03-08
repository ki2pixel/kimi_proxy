"""
Tests unitaires pour la logique de création automatique de sessions basée sur les modèles.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from kimi_proxy.core.auto_session import (
    extract_external_session_id_from_request,
    extract_provider_from_request,
    should_auto_create_session,
)


def test_should_auto_create_session_no_current_session():
    """Test: Pas de session active = créer une nouvelle session."""
    result = should_auto_create_session(
        detected_provider="openai",
        detected_model="nvidia/kimi-k2.5",
        current_session=None
    )
    assert result is True


def test_should_auto_create_session_same_model():
    """Test: Même modèle = ne pas créer de nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "openai",
        "model": "nvidia/kimi-k2.5"
    }
    result = should_auto_create_session(
        detected_provider="openai",
        detected_model="nvidia/kimi-k2.5",
        current_session=current_session
    )
    assert result is False


def test_should_auto_create_session_same_triplet():
    """Test: Même provider, modèle et session externe = pas de nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "managed:kimi-code",
        "model": "kimi-for-coding",
        "external_session_id": "kimi-session-001",
    }
    result = should_auto_create_session(
        detected_provider="managed:kimi-code",
        detected_model="kimi-for-coding",
        current_session=current_session,
        detected_external_session_id="kimi-session-001",
    )
    assert result is False


def test_should_auto_create_session_different_model_same_provider():
    """Test: Modèles différents mais même provider = créer une nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "openai",
        "model": "nvidia/kimi-k2.5"
    }
    result = should_auto_create_session(
        detected_provider="openai",
        detected_model="nvidia/kimi-k2-thinking",
        current_session=current_session
    )
    assert result is True


def test_should_auto_create_session_different_provider_same_model():
    """Test: Providers différents mais même modèle = créer une nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "openai",
        "model": "nvidia/kimi-k2.5"
    }
    result = should_auto_create_session(
        detected_provider="anthropic",
        detected_model="nvidia/kimi-k2.5",
        current_session=current_session
    )
    assert result is True


def test_should_auto_create_session_same_provider_model_different_external_session():
    """Test: Même provider+modèle mais session externe différente = nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "managed:kimi-code",
        "model": "kimi-for-coding",
        "external_session_id": "kimi-session-001",
    }
    result = should_auto_create_session(
        detected_provider="managed:kimi-code",
        detected_model="kimi-for-coding",
        current_session=current_session,
        detected_external_session_id="kimi-session-002",
    )
    assert result is True


def test_should_auto_create_session_fallback_when_external_session_missing():
    """Test: Sans session externe, on garde le fallback historique sur le modèle."""
    current_session = {
        "id": 1,
        "provider": "managed:kimi-code",
        "model": "kimi-for-coding",
    }
    result = should_auto_create_session(
        detected_provider="managed:kimi-code",
        detected_model="kimi-for-coding",
        current_session=current_session,
        detected_external_session_id=None,
    )
    assert result is False


def test_should_auto_create_session_different_model_and_provider():
    """Test: Modèles et providers différents = créer une nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "openai",
        "model": "nvidia/kimi-k2.5"
    }
    result = should_auto_create_session(
        detected_provider="anthropic",
        detected_model="claude-3-opus",
        current_session=current_session
    )
    assert result is True


def test_should_auto_create_session_current_session_no_model():
    """Test: Session actuelle sans modèle = créer une nouvelle session."""
    current_session = {
        "id": 1,
        "provider": "openai"
        # Pas de champ "model"
    }
    result = should_auto_create_session(
        detected_provider="openai",
        detected_model="nvidia/kimi-k2.5",
        current_session=current_session
    )
    # current_model sera None, detected_model est "nvidia/kimi-k2.5" → différent
    assert result is True


def test_extract_provider_from_request_supports_explicit_keys():
    """Test: le provider explicite peut être lu depuis le body ou metadata."""
    assert extract_provider_from_request({"provider": "managed:kimi-code"}) == "managed:kimi-code"
    assert extract_provider_from_request({"metadata": {"provider": "openai"}}) == "openai"


def test_extract_external_session_id_from_request_supports_explicit_keys():
    """Test: l'identifiant de session externe est extrait depuis des clés explicites."""
    assert extract_external_session_id_from_request({"external_session_id": "ext-001"}) == "ext-001"
    assert extract_external_session_id_from_request({"metadata": {"session_external_id": "ext-002"}}) == "ext-002"
    assert extract_external_session_id_from_request({"session": {"external_session_id": "ext-003"}}) == "ext-003"


def test_nvidia_models_distinction():
    """Test: Vérifier que les 8 modèles NVIDIA sont bien distingués."""
    nvidia_models = [
        "nvidia/kimi-k2.5",
        "nvidia/kimi-k2-thinking",
        "nvidia/mistral-large-3",
        "nvidia/llama-3.3-70b",
        "nvidia/gemma-2-27b",
        "nvidia/phi-4-14b",
        "nvidia/deepseek-r1",
        "nvidia/deepseek-v3"
    ]
    
    # Pour chaque paire de modèles, vérifier qu'ils créent des sessions différentes
    for i, model1 in enumerate(nvidia_models):
        for j, model2 in enumerate(nvidia_models):
            if i != j:
                current_session = {
                    "id": 1,
                    "provider": "openai",
                    "model": model1
                }
                result = should_auto_create_session(
                    detected_provider="openai",
                    detected_model=model2,
                    current_session=current_session
                )
                assert result is True, f"Les modèles {model1} et {model2} devraient créer des sessions différentes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])