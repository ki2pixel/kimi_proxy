"""Dépendances communes pour l'API Kimi Proxy."""
import os
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.exceptions import ConfigurationError

security_bearer = HTTPBearer(auto_error=False)

_ENV = os.getenv("KIMI_ENV", "development").strip().lower()
_ADMIN_KEY = os.getenv("KIMI_ADMIN_KEY", "").strip()

if _ENV == "production" and not _ADMIN_KEY:
    raise ConfigurationError(
        message="KIMI_ADMIN_KEY environment variable is mandatory in production mode.",
        config_key="KIMI_ADMIN_KEY",
    )


async def verify_admin_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer),
):
    """Valide la clé admin via Authorization Bearer ou X-Admin-Key."""
    if not _ADMIN_KEY:
        return

    token = credentials.credentials if credentials else request.headers.get("x-admin-key")

    if not token or token.strip() != _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing admin key.",
        )


async def verify_admin_key_x_header(request: Request):
    """Valide la clé admin uniquement via X-Admin-Key.

    Nécessaire pour /v1/chat/completions, où Authorization transporte la clé
    provider du client et ne peut pas servir à l'authentification admin.
    """
    if not _ADMIN_KEY:
        return

    token = request.headers.get("x-admin-key")
    if not token or token.strip() != _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing admin key.",
        )
