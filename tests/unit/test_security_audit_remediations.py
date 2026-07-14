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
def test_ssrf_protection(monkeypatch):
    from kimi_proxy.proxy.passthrough import validate_and_normalize_target_url
    
    # 1. En mode developpement
    monkeypatch.setenv("KIMI_ENV", "development")
    # Loopback doit passer
    url_dev_ok = validate_and_normalize_target_url("http://localhost:8000")
    assert "localhost:8000" in url_dev_ok
    
    # Hôte externe HTTP non-sécurisé doit être rejeté
    with pytest.raises(ValueError, match="HTTP non sécurisé est interdit"):
        validate_and_normalize_target_url("http://api.openai.com")

    # 2. En mode production
    monkeypatch.setenv("KIMI_ENV", "production")
    # Loopback/adresses privées doivent être rejetées
    with pytest.raises(ValueError, match="Le protocole HTTP non sécurisé est interdit"):
         validate_and_normalize_target_url("http://127.0.0.1")
         
    with pytest.raises(ValueError, match="Accès à une adresse IP interdite/privée"):
         # 127.0.0.1 résolu ou passé directement
         validate_and_normalize_target_url("https://127.0.0.1")
         
    # Hôtes non autorisés par l'allowlist par défaut
    with pytest.raises(ValueError, match="pas autorisé par l'allowlist"):
         validate_and_normalize_target_url("https://evil-domain.com/api")
         
    # Hôtes autorisés par l'allowlist
    url_prod_ok = validate_and_normalize_target_url("https://api.openai.com/v1")
    assert url_prod_ok == "https://api.openai.com/v1"


# Test Sanitizer encryption
def test_sanitizer_encryption(monkeypatch):
    from kimi_proxy.features.sanitizer.storage import encrypt_content, decrypt_content
    
    secret_key = "my-super-secret-key"
    original_text = "Ceci est un secret très confidentiel."
    
    encrypted = encrypt_content(original_text, secret_key)
    assert encrypted != original_text
    
    decrypted = decrypt_content(encrypted, secret_key)
    assert decrypted == original_text
