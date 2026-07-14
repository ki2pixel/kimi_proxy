"""
Dépendances communes pour l'API Kimi Proxy.
"""
import os
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..core.exceptions import ConfigurationError

# Sécurité Bearer Token
security_bearer = HTTPBearer(auto_error=False)

# Vérification fail-fast au démarrage en mode production
_ENV = os.getenv("KIMI_ENV", "development").strip().lower()
_ADMIN_KEY = os.getenv("KIMI_ADMIN_KEY", "").strip()

if _ENV == "production" and not _ADMIN_KEY:
    raise ConfigurationError(
        message="KIMI_ADMIN_KEY environment variable is mandatory in production mode.",
        config_key="KIMI_ADMIN_KEY"
    )

async def verify_admin_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer)
):
    """
    Dépendance FastAPI pour valider la clé d'administration.
    - Recherche dans le header Authorization (Bearer token)
    - Recherche alternative dans le header X-Admin-Key
    - Comportement selon le profil KIMI_ENV :
      - production: KIMI_ADMIN_KEY obligatoire. Erreur si absente ou invalide.
      - development / autre : Si KIMI_ADMIN_KEY est définie, validation obligatoire.
        Sinon, fail-open avec avertissement (profil local-dev).
    """
    # Si pas de clé configurée en développement, on laisse passer (fail-open)
    if not _ADMIN_KEY:
        # Avertissement émis une fois au démarrage ou à chaque requête si nécessaire
        return

    # Extraction du token (Bearer ou header X-Admin-Key)
    token = None
    if credentials:
        token = credentials.credentials
    else:
        token = request.headers.get("x-admin-key")
        
    if not token or token.strip() != _ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing admin key."
        )
