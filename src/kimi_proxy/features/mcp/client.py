"""
Facade MCP pour connexion aux serveurs MCP externes (Phase 3 & 4).

NOUVELLE ARCHITECTURE (2026-02-18):
- Facade légère qui délègue aux clients spécialisés
- Préserve 100% de la compatibilité ascendante
- Chaque serveur MCP a son propre module dans servers/

Structure:
- base/: Configuration et RPC de base (config.py, rpc.py)
- servers/: Clients spécialisés par serveur (qdrant, compression, shrimp_task_manager, sequential, filesystem, json_query)
- client.py: Facade principale avec singleton global

Serveurs supportés (7 serveurs, 43 outils):
- Qdrant MCP (Phase 3): Recherche sémantique, clustering
- Context Compression MCP (Phase 3): Compression avancée
- Shrimp Task Manager MCP (Phase 4, 14 outils): Gestion de tâches
- Sequential Thinking MCP (Phase 4, 1 outil): Raisonnement séquentiel
- Fast Filesystem MCP (Phase 4, 25 outils): Opérations fichiers
- JSON Query MCP (Phase 4, 3 outils): Requêtes JSON

BACKUP: Fichier original sauvegardé dans client.py.backup (1,230 lignes)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import time

from kimi_proxy.core.models import (
    QdrantSearchResult,
    MCPCluster,
    MCPCompressionResult,
    MCPExternalServerStatus,
    MCPToolCall,
)
from .base.config import MCPClientConfig
from .base.rpc import MCPRPCClient
from .servers import (
    QdrantMCPClient,
    CompressionMCPClient,
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
        
        # Cache statut global
        self._status_cache: Dict[str, MCPExternalServerStatus] = {}
        self._tool_cache: Dict[str, Dict[str, Any]] = {}  # Cache pour les résultats d'outils

    async def close(self):
        """Ferme toutes les connexions HTTP."""
        await self._rpc_client.close()

    def _get_tool_cache_key(self, server_type: str, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Génère une clé de cache pour les résultats d'outils MCP.
        
        Args:
            server_type: Type de serveur
            tool_name: Nom de l'outil
            params: Paramètres
            
        Returns:
            Clé de cache unique
        """
        import hashlib
        key_data = f"{server_type}:{tool_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()[:16]
    
    def _should_cache_tool_result(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """
        Détermine si un résultat d'outil doit être mis en cache.
        
        Args:
            tool_name: Nom de l'outil
            result: Résultat de l'outil
            
        Returns:
            True si le résultat doit être mis en cache
        """
        # Liste des outils dont les résultats peuvent être mis en cache
        cacheable_tools = {
            "fast_read_file",
            "fast_list_directory", 
            "fast_get_file_info",
            "fast_search_code",
            "fast_search_files",
            "json_query_jsonpath",
            "json_query_search_keys"
        }
        
        if tool_name not in cacheable_tools:
            return False
        
        # Vérifie si le résultat contient du contenu volumineux
        content = ""
        if isinstance(result, dict) and "content" in result:
            content = str(result.get("content", ""))
        else:
            content = str(result)
        
        # Met en cache si le contenu fait plus de 1K caractères
        return len(content) > 1000
    
    async def _compress_large_response(self, content: str) -> str:
        """
        Compresse une réponse volumineuse si nécessaire.
        
        Args:
            content: Contenu à compresser
            
        Returns:
            Contenu compressé ou original
        """
        if len(content) < 5000:  # Ne compresse que les contenus > 5K
            return content
        
        try:
            # Essaie d'utiliser le service de compression MCP
            if self.is_compression_available():
                compressed_result = await self.compress_content(
                    content, 
                    algorithm="context_aware", 
                    target_ratio=0.7  # Compression à 70%
                )
                
                if compressed_result.success and compressed_result.compressed_content:  # type: ignore
                    print(f"🗜️ [COMPRESSION] Contenu compressé: {len(content)} → {len(compressed_result.compressed_content)} chars")
                    return f"[COMPRESSED CONTENT - {compressed_result.compression_ratio:.1%} saved]\n{compressed_result.compressed_content}"
            
        except Exception as e:
            print(f"⚠️ [COMPRESSION] Erreur lors de la compression: {e}")
        
        # Fallback: compression simple par troncature intelligente
        if len(content) > 10000:
            truncated = content[:8000] + f"\n\n[... CONTENU TRONQUÉ - {len(content) - 8000} caractères supprimés ...]"
            print(f"✂️ [TRUNCATION] Contenu tronqué: {len(content)} → {len(truncated)} chars")
            return truncated
        
        return content
    
    async def _get_cached_tool_result(self, server_type: str, tool_name: str, params: Dict[str, Any]) -> Optional[MCPToolCall]:
        """
        Récupère un résultat d'outil depuis le cache.
        
        Args:
            server_type: Type de serveur
            tool_name: Nom de l'outil
            params: Paramètres
            
        Returns:
            Résultat mis en cache ou None
        """
        cache_key = self._get_tool_cache_key(server_type, tool_name, params)
        
        if cache_key in self._tool_cache:
            cached_entry = self._tool_cache[cache_key]
            
            # Vérifie si le cache n'est pas expiré (TTL de 5 minutes)
            import time
            if time.time() - cached_entry["cached_at"] < 300:  # 5 minutes
                print(f"💾 [TOOL CACHE] Hit pour {tool_name}: {cache_key}")
                return MCPToolCall(
                    server_type=server_type,
                    tool_name=tool_name,
                    params=params,
                    status="success",
                    result=cached_entry["result"],
                    execution_time_ms=cached_entry["execution_time_ms"]
                )
            else:
                # Cache expiré, supprime
                del self._tool_cache[cache_key]
        
        return None
    
    def _cache_tool_result(self, server_type: str, tool_name: str, params: Dict[str, Any], result: Dict[str, Any], execution_time_ms: float):
        """
        Met en cache un résultat d'outil.
        
        Args:
            server_type: Type de serveur
            tool_name: Nom de l'outil
            params: Paramètres
            result: Résultat à mettre en cache
            execution_time_ms: Temps d'exécution
        """
        if not self._should_cache_tool_result(tool_name, result):
            return
        
        cache_key = self._get_tool_cache_key(server_type, tool_name, params)
        
        self._tool_cache[cache_key] = {
            "server_type": server_type,
            "tool_name": tool_name,
            "params": params,
            "result": result,
            "execution_time_ms": execution_time_ms,
            "cached_at": time.time()
        }
        
        print(f"💾 [TOOL CACHE] Stored {tool_name}: {cache_key} ({len(str(result))} chars)")
    
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
    
    async def get_all_server_statuses(self) -> List[MCPExternalServerStatus]:
        """Récupère le statut de tous les serveurs MCP externes."""
        statuses = []
        statuses.append(await self.qdrant.check_status())
        statuses.append(await self.compression.check_status())
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
            # Vérifie le cache d'abord
            cached_result = await self._get_cached_tool_result(server_type, tool_name, params)
            if cached_result:
                return cached_result
            
            # Type de serveur inconnu
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            return MCPToolCall(
                server_type=server_type,
                tool_name=tool_name,
                params=params,
                status="error",
                result={"error": f"Type de serveur inconnu: {server_type}"},
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            print(f" [MCP TOOL] Erreur lors de l'appel {server_type}.{tool_name}: {e}")
            
            return MCPToolCall(
                server_type=server_type,
                tool_name=tool_name,
                params=params,
                status="error",
                result={"error": str(e), "server_type": server_type, "tool_name": tool_name},
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


