"""
Client MCP spécialisé pour JSON Query.

Gère les requêtes JSON avancées avec JSONPath.
Performance: <5ms pour requêtes simples, <2s pour fichiers volumineux.
"""
from datetime import datetime
from typing import Dict, Any, List

from ..base.rpc import MCPRPCClient

# Modèles imports avec TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.core.models import JsonQueryResult, MCPPhase4ServerStatus
    from ..base.config import MCPClientConfig


class JsonQueryMCPClient:
    """
    Client spécialisé pour JSON Query MCP.
    
    Supporte 3 outils:
    - json_query_jsonpath: Requêtes JSONPath (ex: $.store.book[*].author)
    - json_query_search_keys: Recherche par clé
    - json_query_search_values: Recherche par valeur
    
    Use cases:
    - Extraction de configuration
    - Validation de schema
    - Analyse de structure JSON
    - Recherche dans données structurées
    
    Performance:
    - JSONPath: <5ms
    - Search: <50ms
    - Fichiers >10MB: <2s
    """
    
    # Liste des outils valides
    VALID_TOOLS = [
        "json_query_jsonpath",
        "json_query_search_keys",
        "json_query_search_values"
    ]
    
    def __init__(self, config: "MCPClientConfig", rpc_client: MCPRPCClient):
        """
        Initialise le client JSON Query MCP.
        
        Args:
            config: Configuration MCP
            rpc_client: Client RPC de base
        """
        self.config = config
        self.rpc_client = rpc_client
        self._status: Optional["MCPPhase4ServerStatus"] = None
    
    async def check_status(self) -> "MCPPhase4ServerStatus":
        """
        Vérifie le statut du serveur JSON Query MCP.
        
        Teste avec une recherche simple.
        
        Returns:
            Status du serveur
        """
        from kimi_proxy.core.models import MCPPhase4ServerStatus
        
        try:
            start_time = datetime.now()
            
            # Test avec une recherche de clés simple
            result = await self.rpc_client.make_rpc_call(
                server_url=self.config.json_query_url,
                method="json_query_search_keys",
                params={
                    "file_path": "test.json",
                    "query": "test"
                },
                timeout_ms=2000.0,
                api_key=self.config.json_query_api_key
            )
            
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            self._status = MCPPhase4ServerStatus(
                name="json-query-mcp",
                type="json_query",
                url=self.config.json_query_url,
                connected=True,
                last_check=datetime.now().isoformat(),
                latency_ms=latency_ms,
                tools_count=len(self.VALID_TOOLS),
                capabilities=["jsonpath", "key_search", "value_search"]
            )
            return self._status
            
        except Exception:
            self._status = MCPPhase4ServerStatus(
                name="json-query-mcp",
                type="json_query",
                url=self.config.json_query_url,
                connected=False,
                last_check=datetime.now().isoformat(),
                error_count=1,
                tools_count=len(self.VALID_TOOLS),
                capabilities=[]
            )
            return self._status
    
    async def call_tool(
        self,
        tool_name: str,
        file_path: str,
        query: str,
        limit: int = 5
    ) -> "JsonQueryResult":
        """
        Appelle un outil JSON Query avec validation.
        
        Args:
            tool_name: Nom de l'outil (json_query_jsonpath, json_query_search_keys, json_query_search_values)
            file_path: Chemin du fichier JSON à analyser
            query: Requête (JSONPath ou terme de recherche)
            limit: Nombre maximum de résultats
            
        Returns:
            Résultat avec les matches trouvés
            
        JsonQueryResult:
            - success: Bool
            - query: Requête originale
            - file_path: Fichier analysé
            - results: Liste des résultats
            - execution_time_ms: Temps d'exécution
            
        Example:
            >>> # JSONPath: extraire tous les titres de livres
            >>> result = await client.call_tool(
            ...     "json_query_jsonpath",
            ...     file_path="books.json",
            ...     query="$.store.book[*].title"
            ... )
            >>> 
            >>> # Recherche de clés
            >>> result = await client.call_tool(
            ...     "json_query_search_keys",
            ...     file_path="config.json",
            ...     query="api_key"
            ... )
            >>> 
            >>> # Recherche de valeurs
            >>> result = await client.call_tool(
            ...     "json_query_search_values",
            ...     file_path="test.json",
            ...     query="localhost"
            ... )
        """
        from kimi_proxy.core.models import JsonQueryResult
        
        if tool_name not in self.VALID_TOOLS:
            return JsonQueryResult(
                success=False,
                query=query,
                file_path=file_path,
                error=f"Outil invalide: {tool_name}. Outils valides: {', '.join(self.VALID_TOOLS)}"
            )
        
        start_time = datetime.now()
        
        try:
            result = await self.rpc_client.make_rpc_call(
                server_url=self.config.json_query_url,
                method=tool_name,
                params={
                    "file_path": file_path,
                    "query": query,
                    "limit": limit
                },
                timeout_ms=self.config.json_query_timeout_ms,
                api_key=self.config.json_query_api_key
            )
            
            if not result or not isinstance(result, dict):
                return JsonQueryResult(
                    success=False,
                    query=query,
                    file_path=file_path,
                    error="Aucune réponse du serveur"
                )
            
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            return JsonQueryResult(
                success=True,
                query=query,
                file_path=file_path,
                results=result.get("results", []),
                execution_time_ms=execution_time_ms
            )
        except Exception as e:
            return JsonQueryResult(
                success=False,
                query=query,
                file_path=file_path,
                error=str(e)
            )
    
    # Helpers pour les requêtes courantes
    
    async def jsonpath(
        self,
        file_path: str,
        jsonpath_expr: str
    ) -> "JsonQueryResult":
        """
        Requête JSONPath (helper pour json_query_jsonpath).
        
        Exemples JSONPath:
        - $.store.book[*].author              # Tous les auteurs
        - $.store.book[?(@.price < 10)].title  # Livres pas chers
        - $..author                            # Auteurs à tous les niveaux
        
        Args:
            file_path: Fichier JSON
            jsonpath_expr: Expression JSONPath
            
        Returns:
            Résultats extraits
        """
        return await self.call_tool(
            "json_query_jsonpath",
            file_path=file_path,
            query=jsonpath_expr
        )
    
    async def search_keys(self, file_path: str, key_name: str) -> "JsonQueryResult":
        """
        Recherche des clés par nom (helper pour json_query_search_keys).
        
        Args:
            file_path: Fichier JSON
            key_name: Nom de clé à chercher
            
        Returns:
            Clés trouvées avec chemins
        """
        return await self.call_tool(
            "json_query_search_keys",
            file_path=file_path,
            query=key_name
        )
    
    async def search_values(self, file_path: str, value: str, limit: int = 10) -> "JsonQueryResult":
        """
        Recherche des valeurs (helper pour json_query_search_values).
        
        Args:
            file_path: Fichier JSON
            value: Valeur à chercher
            limit: Nombre max de résultats
            
        Returns:
            Valeurs trouvées avec contexte
        """
        return await self.call_tool(
            "json_query_search_values",
            file_path=file_path,
            query=value,
            limit=limit
        )
    
    def is_available(self) -> bool:
        """
        Vérifie si JSON Query est disponible.
        
        Returns:
            True si le dernier check était connecté
        """
        return self._status is not None and self._status.connected
