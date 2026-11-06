"""
Tests unitaires pour les remédiations de sécurité issues de l'audit 2026.
"""
import ast
import pytest

# Test eval replacement
def test_eval_replacement():
    
    # Payload hostile d'injection de code
    hostile_input = "{'a': __import__('os').system('echo INJECTED')}"
    # ast.literal_eval doit rejeter cela avec ValueError ou une exception similaire
    with pytest.raises(ValueError):
        ast.literal_eval(hostile_input)


# Test SSRF protection
@pytest.mark.asyncio
async def test_ssrf_protection(monkeypatch):
    from kimi_proxy.proxy.passthrough import validate_and_normalize_target_url

    # 1. En mode developpement
    monkeypatch.setenv("KIMI_ENV", "development")
    url_dev_ok = await validate_and_normalize_target_url("http://localhost:8000")
    assert "localhost:8000" in url_dev_ok

    with pytest.raises(ValueError, match="HTTP non sécurisé est interdit"):
        await validate_and_normalize_target_url("http://api.openai.com")

    # 2. En mode production
    monkeypatch.setenv("KIMI_ENV", "production")
    with pytest.raises(ValueError, match="Le protocole HTTP non sécurisé est interdit"):
        await validate_and_normalize_target_url("http://127.0.0.1")

    with pytest.raises(ValueError, match="Accès à une adresse IP interdite/privée"):
        await validate_and_normalize_target_url("https://127.0.0.1")

    with pytest.raises(ValueError, match="pas autorisé par l'allowlist"):
        await validate_and_normalize_target_url("https://evil-domain.com/api")

    url_prod_ok = await validate_and_normalize_target_url("https://api.openai.com/v1")
    assert url_prod_ok == "https://api.openai.com/v1"
