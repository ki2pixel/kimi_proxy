"""
RPC client MCP avec retry et timeouts.

Fournit MCPRPCClient pour les appels JSON-RPC 2.0 vers les serveurs MCP.
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import httpx

from ....core.exceptions import KimiProxyError


class MCPClientError(KimiProxyError):
    """Erreur de client MCP."""
    pass


class MCPConnectionError(MCPClientError):
    """Erreur de connexion MCP."""
    pass


class MCPTimeoutError(MCPClientError):
    """Timeout serveur MCP."""
    pass


class MCPRPCClient:
    """
    Client RPC MCP avec retry intégré.
    
    Gère les appels JSON-RPC 2.0 vers les serveurs MCP avec:
    - Retry automatique avec backoff exponentiel
    - Timeouts configurables
    - Pool de connexions HTTP optimisé
    """
    
    def __init__(self, max_retries: int = 3, retry_delay_ms: float = 100.0):
        """
        Initialise le client RPC MCP.
        
        Args:
            max_retries: Nombre maximum de tentatives
            retry_delay_ms: Délai initial entre les tentatives (ms)
        """
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """
        Récupère ou crée le client HTTP avec pool de connexions.
        
        Returns:
            Client HTTP async
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20
                )
            )
        return self._http_client
    
    async def close(self):
        """Ferme le client HTTP de manière propre."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
    
    async def make_rpc_call(
        self,
        server_url: str,
        method: str,
        params: Dict[str, Any],
        timeout_ms: float = 5000.0,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Effectue un appel JSON-RPC 2.0 avec retry et backoff exponentiel.
        
        Args:
            server_url: URL du serveur MCP (ex: http://localhost:6333)
            method: Méthode à appeler (ex: "search", "compress")
            params: Paramètres de la méthode (dict)
            timeout_ms: Timeout en millisecondes (par défaut: 5000ms)
            api_key: Clé API optionnelle pour l'authentification
            
        Returns:
            Dict[str, Any]: Résultat de l'appel RPC (clé "result")
            
        Raises:
            MCPClientError: Erreur RPC retournée par le serveur
            MCPConnectionError: Erreur de connexion réseau
            MCPTimeoutError: Timeout après toutes les tentatives
            
        Example:
            >>> client = MCPRPCClient()
            >>> result = await client.make_rpc_call(
            ...     "http://localhost:6333",
            ...     "search",
            ...     {"collection": "test", "query": "hello"},
            ...     timeout_ms=1000.0
            ... )
            >>> print(result.get("hits", []))
        """
        client = await self._get_client()
        
        # Construit le payload JSON-RPC 2.0
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": datetime.now().timestamp()  # ID unique basé sur le timestamp
        }
        
        # En-têtes
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        timeout = httpx.Timeout(timeout_ms / 1000.0)  # Convertit ms → secondes
        
        # Boucle de retry avec backoff exponentiel
        for attempt in range(self.max_retries):
            try:
                start_time = datetime.now()
                
                # Appel HTTP POST vers /rpc
                response = await client.post(
                    f"{server_url}/rpc",
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                # Vérifie la réponse HTTP
                if response.status_code == 200:
                    result = response.json()
                    
                    # Vérifie si le serveur a retourné une erreur RPC
                    if "error" in result:
                        raise MCPClientError(f"Erreur RPC: {result['error']}")
                    
                    # Retourne le résultat
                    return result.get("result", {})
                else:
                    # Erreur HTTP
                    raise MCPConnectionError(
                        f"HTTP {response.status_code}: {response.text}"
                    )
                    
            except httpx.TimeoutException:
                # Timeout: retry si ce n'est pas la dernière tentative
                if attempt == self.max_retries - 1:
                    raise MCPTimeoutError(
                        f"Timeout après {self.max_retries} tentatives (timeout_ms={timeout_ms})"
                    )
                
                # Backoff exponentiel: delay * (attempt + 1)
                backoff_delay = self.retry_delay_ms / 1000.0 * (attempt + 1)
                await asyncio.sleep(backoff_delay)
                
            except httpx.ConnectError as e:
                # Erreur de connexion: retry si ce n'est pas la dernière tentative
                if attempt == self.max_retries - 1:
                    raise MCPConnectionError(
                        f"Échec de connexion après {self.max_retries} tentatives: {str(e)}"
                    )
                
                # Backoff exponentiel
                backoff_delay = self.retry_delay_ms / 1000.0 * (attempt + 1)
                await asyncio.sleep(backoff_delay)
                
            except Exception as e:
                # Erreur inattendue
                if attempt == self.max_retries - 1:
                    raise MCPConnectionError(
                        f"Erreur inattendue après {self.max_retries} tentatives: {str(e)}"
                    )
                
                # Backoff exponentiel
                backoff_delay = self.retry_delay_ms / 1000.0 * (attempt + 1)
                await asyncio.sleep(backoff_delay)
        
        # Si on arrive ici, toutes les tentatives ont échoué
        return {}
