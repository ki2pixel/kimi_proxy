"""Dépendances communes pour l'API Kimi Proxy."""
import os
import secrets

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..core.exceptions import ConfigurationError

security_bearer = HTTPBearer(auto_error=False)


def _get_admin_key() -> str:
    """Relit la configuration d'authentification à chaque requête.

    La lecture dynamique permet aux tests unitaires de surcharger l'environnement
    via ``monkeypatch`` sans recharger le module.
    """
    env = os.getenv("KIMI_ENV", "development").strip().lower()
    admin_key = os.getenv("KIMI_ADMIN_KEY", "").strip()
    if env == "production" and not admin_key:
        raise ConfigurationError(
            message="La variable d'environnement KIMI_ADMIN_KEY est obligatoire en mode production.",
            config_key="KIMI_ADMIN_KEY",
        )
    return admin_key


# Garde de démarrage : une production sans clé admin doit échouer immédiatement.
if (
    os.getenv("KIMI_ENV", "development").strip().lower() == "production"
    and not os.getenv("KIMI_ADMIN_KEY", "").strip()
):
    raise ConfigurationError(
        message="La variable d'environnement KIMI_ADMIN_KEY est obligatoire en mode production.",
        config_key="KIMI_ADMIN_KEY",
    )


def _token_matches(token: str | None, admin_key: str) -> bool:
    """Compare le jeton en temps constant, y compris pour des caractères non ASCII."""
    if not token:
        return False
    return secrets.compare_digest(
        token.strip().encode("utf-8"),
        admin_key.encode("utf-8"),
    )


async def verify_admin_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> None:
    """Valide la clé admin via Authorization Bearer ou X-Admin-Key."""
    admin_key = _get_admin_key()
    if not admin_key:
        return

    token = credentials.credentials if credentials else request.headers.get("x-admin-key")
    if not _token_matches(token, admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autorisé : clé d'administration invalide ou manquante.",
        )


async def verify_admin_key_x_header(request: Request) -> None:
    """Valide la clé admin uniquement via X-Admin-Key.

    Nécessaire pour /v1/chat/completions, où Authorization transporte la clé
    provider du client et ne peut pas servir à l'authentification admin.
    """
    admin_key = _get_admin_key()
    if not admin_key:
        return

    token = request.headers.get("x-admin-key")
    if not _token_matches(token, admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autorisé : clé d'administration invalide ou manquante.",
        )
