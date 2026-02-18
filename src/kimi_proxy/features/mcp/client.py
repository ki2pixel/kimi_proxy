"""
Facade MCP pour connexion aux serveurs MCP externes (Phase 3 & 4).

NOUVELLE ARCHITECTURE (2026-02-18):
- Facade légère qui délègue aux clients spécialisés
- Préserve 100% de la compatibilité ascendante
- Chaque serveur MCP a son propre module dans servers/

Structure:
- base/: Configuration et RPC de base (config.py, rpc.py)
- servers/: Clients spécialisés par serveur (qdrant, compression, task_master, sequential, filesystem, json_query)
- client.py: Facade principale avec singleton global

Serveurs supportés (7 serveurs, 43 outils):
- Qdrant MCP (Phase 3): Recherche sémantique, clustering
- Context Compression MCP (Phase 3): Compression avancée
- Task Master MCP (Phase 4, 14 outils): Gestion de tâches
- Sequential Thinking MCP (Phase 4, 1 outil): Raisonnement séquentiel
- Fast Filesystem MCP (Phase 4, 25 outils): Opérations fichiers
- JSON Query MCP (Phase 4, 3 outils): Requêtes JSON

BACKUP: Fichier original sauvegardé dans client.py.backup (1,230 lignes)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from kimi_proxy.core.models import (
    QdrantSearchResult,
    MCPCluster,
    MCPCompressionResult,
    MCPExternalServerStatus,
    MCPPhase4ServerStatus,
    TaskMasterTask,
    TaskMasterStats,
    SequentialThinkingStep,
    FileSystemResult,
    JsonQueryResult,
    MCPToolCall,
)
from .base.config import MCPClientConfig
from .base.rpc import MCPRPCClient, MCPClientError, MCPConnectionError, MCPTimeoutError
from .servers import (
    QdrantMCPClient,
    CompressionMCPClient,
    TaskMasterMCPClient,
    SequentialThinkingMCPClient,
    FileSystemMCPClient,
    JsonQueryMCPClient,
)


class MCPExternalClient:
    """
    Facade pour tous les serveurs MCP externes.
    
    Délègue l'implémentation aux clients spécialisés pour maintenir la séparation des responsabilités.
    
    Chaque client spécialisé gère:
    - Configuration spécifique
    - API du serveur MCP
    - Gestion d'erreurs et retry
    - Métriques de performance
    
    Préserve l'API du client original pour compatibilité ascendante.
    """
    
    def __init__(self, config: Optional[MCPClientConfig] = None):
        """
        Initialise la facade MCP.
        
        Args:
            config: Configuration MCP (optionnel, chargée depuis config.toml par défaut)
        """
        self.config = config or MCPClientConfig()
        self._rpc_client = MCPRPCClient(
            max_retries=self.config.max_retries,
            retry_delay_ms=self.config.retry_delay_ms
        )
        
        # Instancie les clients spécialisés
        self.qdrant = QdrantMCPClient(self.config, self._rpc_client)
        self.compression = CompressionMCPClient(self.config, self._rpc_client)
        self.task_master = TaskMasterMCPClient(self.config, self._rpc_client)
        self.sequential = SequentialThinkingMCPClient(self.config, self._rpc_client)
        self.filesystem = FileSystemMCPClient(self.config, self._rpc_client)
        self.json_query = JsonQueryMCPClient(self.config, self._rpc_client)
        
        # Cache statut global
        self._status_cache: Dict[str, MCPExternalServerStatus] = {}
    
    async def close(self):
        """Ferme toutes les connexions HTTP."""
        await self._rpc_client.close()
    
    # ========================================================================
    # Qdrant - Recherche sémantique
    # ========================================================================
    
    async def check_qdrant_status(self) -> MCPExternalServerStatus:
        """Vérifie le statut du serveur Qdrant MCP."""  
        status = await self.qdrant.check_status()
        self._status_cache["qdrant"] = status
        return status
    
    async def search_similar(self, query: str, limit: int = 5, score_threshold: float = 0.7) -> List[QdrantSearchResult]:
        """Recherche sémantique via Qdrant MCP."""
        return await self.qdrant.search_similar(query, limit, score_threshold)
    
    async def store_memory_vector(self, content: str, memory_type: str = "episodic", metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Stocke un vecteur mémoire dans Qdrant."""
        return await self.qdrant.store_vector(content, memory_type, metadata)
    
    async def find_redundant_memories(self, content: str, similarity_threshold: float = 0.85) -> List[str]:
        """Détecte les mémoires redondantes."""
        return await self.qdrant.find_redundant(content, similarity_threshold)
    
    async def cluster_memories(self, session_id: int, min_cluster_size: int = 3) -> List[MCPCluster]:
        """Clusterise les mémoires d'une session."""
        return await self.qdrant.cluster_memories(session_id, min_cluster_size)
    
    # ========================================================================
    # Compression - Compression contextuelle
    # ========================================================================
    
    async def check_compression_status(self) -> MCPExternalServerStatus:
        """Vérifie le statut du serveur Context Compression MCP."""
        status = await self.compression.check_status()
        self._status_cache["compression"] = status
        return status
    
    async def compress_content(self, content: str, algorithm: str = "context_aware", target_ratio: float = 0.5) -> MCPCompressionResult:
        """Compresse du contenu via Context Compression MCP."""
        return await self.compression.compress(content, algorithm, target_ratio)
    
    async def decompress_content(self, compressed_data: str, algorithm: str = "zlib") -> str:
        """Décompresse du contenu."""
        return await self.compression.decompress(compressed_data, algorithm)
    
    # ========================================================================
    # Task Master - Gestion de tâches (Phase 4)
    # ========================================================================
    
    async def check_task_master_status(self) -> MCPPhase4ServerStatus:
        """Vérifie le statut du serveur Task Master MCP."""
        status = await self.task_master.check_status()
        self._status_cache["task_master"] = status
        return status
    
    async def call_task_master_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Appelle un outil Task Master."""
        return await self.task_master.call_tool(tool_name, params)
    
    async def get_task_master_tasks(self, status_filter: Optional[str] = None) -> List[TaskMasterTask]:
        """Récupère les tâches Task Master."""
        return await self.task_master.get_tasks(status_filter)
    
    async def get_task_master_stats(self) -> TaskMasterStats:
        """Récupère les statistiques Task Master."""
        return await self.task_master.get_stats()
    
    # ========================================================================
    # Sequential Thinking - Raisonnement séquentiel (Phase 4)
    # ========================================================================
    
    async def check_sequential_thinking_status(self) -> MCPPhase4ServerStatus:
        """Vérifie le statut du serveur Sequential Thinking MCP."""
        status = await self.sequential.check_status()
        self._status_cache["sequential_thinking"] = status
        return status
    
    async def call_sequential_thinking(
        self,
        thought: str,
        thought_number: int = 1,
        total_thoughts: int = 5,
        next_thought_needed: bool = True,
        available_mcp_tools: Optional[List[str]] = None
    ) -> SequentialThinkingStep:
        """Appelle l'outil de raisonnement séquentiel."""
        return await self.sequential.call_tool(
            thought, thought_number, total_thoughts, next_thought_needed, available_mcp_tools
        )
    
    # ========================================================================
    # Fast Filesystem - Opérations fichiers (Phase 4)
    # ========================================================================
    
    async def check_fast_filesystem_status(self) -> MCPPhase4ServerStatus:
        """Vérifie le statut du serveur Fast Filesystem MCP."""
        status = await self.filesystem.check_status()
        self._status_cache["fast_filesystem"] = status
        return status
    
    async def call_fast_filesystem_tool(self, tool_name: str, params: Dict[str, Any]) -> FileSystemResult:
        """Appelle un outil Fast Filesystem.
        
        Exemple d'outils valides:
        - fast_read_file
        - fast_write_file
        - fast_search_code
        - fast_list_directory
        - fast_edit_block
        - fast_copy_file
        - fast_delete_file
        - ... (25 outils au total)
        """
        return await self.filesystem.call_tool(tool_name, params)
    
    # Helpers courants pour filesystem
    async def fast_read_file(self, path: str, line_count: Optional[int] = None) -> FileSystemResult:
        """Lit un fichier."""
        return await self.filesystem.read_file(path, line_count)
    
    async def fast_write_file(self, path: str, content: str, append: bool = False) -> FileSystemResult:
        """Écrit dans un fichier."""
        return await self.filesystem.write_file(path, content, append)
    
    async def fast_search_code(self, path: str, pattern: str, max_results: int = 50) -> FileSystemResult:
        """Recherche dans le code."""  
        return await self.filesystem.search_code(path, pattern, max_results)
    
    async def fast_list_directory(self, path: str, recursive: bool = False) -> FileSystemResult:
        """Liste un répertoire."""
        return await self.filesystem.list_directory(path, recursive)
    
    # ========================================================================
    # JSON Query - Requêtes JSON (Phase 4)
    # ========================================================================
    
    async def check_json_query_status(self) -> MCPPhase4ServerStatus:
        """Vérifie le statut du serveur JSON Query MCP."""
        status = await self.json_query.check_status()
        self._status_cache["json_query"] = status
        return status
    
    async def call_json_query_tool(self, tool_name: str, file_path: str, query: str, limit: int = 5) -> JsonQueryResult:
        """Appelle un outil JSON Query.
        
        Outils valides:
        - json_query_jsonpath
        - json_query_search_keys  
        - json_query_search_values
        """
        return await self.json_query.call_tool(tool_name, file_path, query, limit)
    
    async def jsonpath_query(self, file_path: str, jsonpath_expr: str) -> JsonQueryResult:
        """Requête JSONPath."""
        return await self.json_query.jsonpath(file_path, jsonpath_expr)
    
    async def search_json_keys(self, file_path: str, key_name: str) -> JsonQueryResult:
        """Recherche de clés JSON."""
        return await self.json_query.search_keys(file_path, key_name)
    
    async def search_json_values(self, file_path: str, value: str, limit: int = 10) -> JsonQueryResult:
        """Recherche de valeurs JSON."""
        return await self.json_query.search_values(file_path, value, limit)
    
    # ========================================================================
    # Statuts globaux
    # ========================================================================
    
    async def get_all_server_statuses(self) -> List[MCPExternalServerStatus]:
        """Récupère le statut de tous les serveurs MCP externes."""
        statuses = []
        statuses.append(await self.qdrant.check_status())
        statuses.append(await self.compression.check_status())
        return statuses
    
    async def get_all_phase4_server_statuses(self) -> List[MCPPhase4ServerStatus]:
        """Récupère le statut de tous les serveurs MCP Phase 4."""
        statuses = []
        statuses.append(await self.task_master.check_status())
        statuses.append(await self.sequential.check_status())
        statuses.append(await self.filesystem.check_status())
        statuses.append(await self.json_query.check_status())
        return statuses
    
    # ========================================================================
    # Disponibilité rapide (cache)
    # ========================================================================
    
    def is_qdrant_available(self) -> bool:
        """Vérifie si Qdrant est disponible."""
        return self.qdrant.is_available()
    
    def is_compression_available(self) -> bool:
        """Vérifie si le serveur de compression est disponible."""
        return self.compression.is_available()
    
    def is_task_master_available(self) -> bool:
        """Vérifie si Task Master est disponible."""
        return self.task_master.is_available()
    
    def is_sequential_thinking_available(self) -> bool:
        """Vérifie si Sequential Thinking est disponible."""
        return self.sequential.is_available()
    
    def is_fast_filesystem_available(self) -> bool:
        """Vérifie si Fast Filesystem est disponible."""
        return self.filesystem.is_available()
    
    def is_json_query_available(self) -> bool:
        """Vérifie si JSON Query est disponible."""
        return self.json_query.is_available()
    
    # ========================================================================
    # API générique (compatibilité ascendante)
    # ========================================================================
    
    async def call_mcp_tool(
        self,
        server_type: str,
        tool_name: str,
        params: Dict[str, Any]
    ) -> MCPToolCall:
        """
        Appelle un outil MCP de manière générique (compatibilité ascendante).
        
        Args:
            server_type: Type de serveur
            tool_name: Nom de l'outil
            params: Paramètres de l'outil
            
        Returns:
            Résultat de l'appel
        """
        start_time = datetime.now()
        
        try:
            if server_type == "task_master":
                result = await self.call_task_master_tool(tool_name, params)
            elif server_type == "sequential_thinking":
                step = await self.call_sequential_thinking(
                    thought=params.get("thought", ""),
                    thought_number=params.get("thought_number", 1),
                    total_thoughts=params.get("total_thoughts", 5),
                    next_thought_needed=params.get("next_thought_needed", True)
                )
                result = {
                    "step_number": step.step_number,
                    "thought": step.thought,
                    "next_thought_needed": step.next_thought_needed,
                    "total_thoughts": step.total_thoughts,
                    "branches": step.branches
                }
            elif server_type == "fast_filesystem":
                fs_result = await self.call_fast_filesystem_tool(tool_name, params)
                result = {
                    "success": fs_result.success,
                    "path": fs_result.path,
                    "operation": fs_result.operation,
                    "content": fs_result.content,
                    "bytes_affected": fs_result.bytes_affected
                }
            elif server_type == "json_query":
                jq_result = await self.call_json_query_tool(
                    tool_name=tool_name,
                    file_path=params.get("file_path", ""),
                    query=params.get("query", ""),
                    limit=params.get("limit", 5)
                )
                result = {
                    "success": jq_result.success,
                    "query": jq_result.query,
                    "file_path": jq_result.file_path,
                    "results": jq_result.results,
                    "execution_time_ms": jq_result.execution_time_ms
                }
            else:
                execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
                return MCPToolCall(
                    server_type=server_type,
                    tool_name=tool_name,
                    params=params,
                    status="error",
                    result={"error": f"Type de serveur inconnu: {server_type}"},
                    execution_time_ms=execution_time_ms
                )
            
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            return MCPToolCall(
                server_type=server_type,
                tool_name=tool_name,
                params=params,
                status="success",
                result=result,
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            return MCPToolCall(
                server_type=server_type,
                tool_name=tool_name,
                params=params,
                status="error",
                result={"error": str(e)},
                execution_time_ms=execution_time_ms
            )


# Singleton global (préservé pour compatibilité ascendante avec les 15+ routes API)
_mcp_client: Optional[MCPExternalClient] = None


def get_mcp_client(config: Optional[MCPClientConfig] = None) -> MCPExternalClient:
    """
    Récupère le client MCP global avec config chargée depuis config.toml.
    
    Args:
        config: Configuration MCP (optionnel)
        
    Returns:
        Instance singleton de MCPExternalClient
    """
    global _mcp_client
    if _mcp_client is None:
        if config is None:
            # Charge la config depuis config.toml
            try:
                from kimi_proxy.config.loader import get_config
                toml_config = get_config()
                config = MCPClientConfig.from_toml(toml_config)
            except Exception:
                # Fallback: config par défaut
                config = MCPClientConfig()
        
        _mcp_client = MCPExternalClient(config)
    return _mcp_client


def reset_mcp_client():
    """Réinitialise le client MCP global (pour tests)."""
    global _mcp_client
    _mcp_client = None
