"""
Client HTTPX pour le proxy avec timeouts configurables et retry.

Pourquoi cette complexité:
- Les providers ont des comportements différents (latence, timeouts)
- Le streaming nécessite des timeouts plus longs
- Les retries doivent être intelligents (pas sur les 4xx)
"""
from typing import Dict, Any, Optional, Callable
import asyncio

import httpx


# Timeouts par provider (secondes)
# Pourquoi: certains providers sont plus lents ou ont des limites différentes
PROVIDER_TIMEOUTS = {
    "gemini": 180.0,      # Gemini peut être lent sur les gros contextes
    "kimi": 120.0,        # Kimi est généralement rapide
    "nvidia": 150.0,      # NVIDIA peut avoir des cold starts
    "mistral": 120.0,
    "openrouter": 150.0,  # OpenRouter fait du routing
    "siliconflow": 120.0,
    "groq": 60.0,         # Groq est ultra-rapide
    "cerebras": 60.0,     # Cerebras aussi
    "default": 120.0
}


class ProxyClient:
    """
    Client HTTP pour le proxy vers les APIs LLM.
    
    Gère:
    - Timeouts configurables par provider
    - Retry avec backoff exponentiel
    - Gestion des connexions
    """
    
    def __init__(
        self, 
        timeout: float = 120.0,
        max_retries: int = 2,
        retry_delay: float = 1.0
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> httpx.AsyncClient:
        # Pourquoi timeout tuple: (connect, read, write, pool)
        # Le read timeout est critique pour le streaming
        timeout = httpx.Timeout(self.timeout, connect=10.0)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            # Pourquoi ces limits: évite l'épuisement des connexions
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50
            )
        )
        return self._client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    def build_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        content: str
    ) -> httpx.Request:
        """Construit une requête HTTPX."""
        return httpx.Request(method, url, headers=headers, content=content)
    
    async def send_streaming(
        self,
        request: httpx.Request,
        provider_type: str = "openai"
    ) -> httpx.Response:
        """
        Envoie une requête en mode streaming avec retry.
        
        Pourquoi retry seulement sur certaines erreurs:
        - 5xx: peut être temporaire, on retry
        - ReadError/ConnectError: problème réseau, on retry
        - 4xx: erreur client, on ne retry pas
        """
        timeout = PROVIDER_TIMEOUTS.get(provider_type, self.timeout)
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            client = None
            try:
                # Nouveau client à chaque tentative (évite connexion corrompue)
                timeout_config = httpx.Timeout(timeout, connect=10.0)
                client = httpx.AsyncClient(timeout=timeout_config)
                
                response = await client.send(request, stream=True)
                
                # Pourquoi on retourne client avec response: le stream
                # a besoin que le client reste vivant
                response._client_ref = client  # Hack pour garder référence
                return response
                
            except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Backoff exponentiel
                    print(f"⚠️  [CLIENT] Retry {attempt + 1}/{self.max_retries} après {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                    if client:
                        await client.aclose()
                    continue
                raise
                
            except Exception:
                if client:
                    await client.aclose()
                raise
        
        # Ne devrait pas arriver, mais par sécurité
        if last_error:
            raise last_error
        raise httpx.ConnectError("Échec après retries")
    
    async def send(
        self,
        request: httpx.Request,
        provider_type: str = "openai"
    ) -> httpx.Response:
        """Envoie une requête et retourne la réponse complète avec retry."""
        timeout = PROVIDER_TIMEOUTS.get(provider_type, self.timeout)
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                timeout_config = httpx.Timeout(timeout, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    return await client.send(request, stream=False)
                    
            except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"⚠️  [CLIENT] Retry {attempt + 1}/{self.max_retries} après {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                    continue
                raise
        
        if last_error:
            raise last_error
        raise httpx.ConnectError("Échec après retries")


def create_proxy_client(
    timeout: float = 120.0,
    max_retries: int = 2,
    retry_delay: float = 1.0
) -> ProxyClient:
    """
    Crée un client proxy.
    
    Args:
        timeout: Timeout en secondes
        max_retries: Nombre de retries sur erreur réseau
        retry_delay: Délai initial entre retries (backoff exponentiel)
        
    Returns:
        Instance de ProxyClient
    """
    return ProxyClient(
        timeout=timeout,
        max_retries=max_retries,
        retry_delay=retry_delay
    )
