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
from kimi_proxy.core.tokens import count_tokens_text
from kimi_proxy.core.constants import MCP_MAX_RESPONSE_TOKENS, MCP_CHUNK_OVERLAP_TOKENS
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


def chunk_large_response(content: str, max_tokens_per_chunk: int = MCP_MAX_RESPONSE_TOKENS, overlap_tokens: int = MCP_CHUNK_OVERLAP_TOKENS) -> List[str]:
    """
    Chunk une réponse MCP volumineuse en morceaux plus petits.
    
    Args:
        content: Contenu à chunker
        max_tokens_per_chunk: Nombre max de tokens par chunk
        overlap_tokens: Nombre de tokens de chevauchement entre chunks
        
    Returns:
        Liste des chunks
    """
    if not content:
        return [""]
    
    # Compte les tokens totaux
    total_tokens = count_tokens_text(content)
    
    # Si ça rentre dans un seul chunk, pas besoin de chunker
    if total_tokens <= max_tokens_per_chunk:
        return [content]
    
    print(f"🔄 [MCP CHUNKING] Réponse de {total_tokens:,} tokens > {max_tokens_per_chunk:,} limite, chunking...")
    
    chunks = []
    start_idx = 0
    
    while start_idx < len(content):
        # Trouve la fin du chunk (par tokens, pas par caractères)
        chunk_end_idx = _find_chunk_boundary(content, start_idx, max_tokens_per_chunk)
        
        if chunk_end_idx <= start_idx:
            # Cas limite : chunk trop petit, prend tout ce qui reste
            chunk = content[start_idx:]
            if chunk:
                chunks.append(chunk)
            break
        
        # Extrait le chunk avec overlap
        chunk = content[start_idx:chunk_end_idx]
        chunks.append(chunk)
        
        # Avance avec overlap négatif pour éviter les coupures au milieu des mots
        overlap_start = max(start_idx, chunk_end_idx - overlap_tokens * 4)  # Approximation caractères
        next_start = _find_word_boundary(content, overlap_start)
        
        if next_start <= start_idx:
            # Évite la boucle infinie
            start_idx = chunk_end_idx
        else:
            start_idx = next_start
    
    print(f"✅ [MCP CHUNKING] Produit {len(chunks)} chunks")
    return chunks


def _find_chunk_boundary(text: str, start_idx: int, max_tokens: int) -> int:
    """
    Trouve la limite d'un chunk par nombre de tokens.
    """
    current_tokens = 0
    current_idx = start_idx
    
    while current_idx < len(text) and current_tokens < max_tokens:
        # Trouve le prochain mot
        word_start = current_idx
        while current_idx < len(text) and text[current_idx].isspace():
            current_idx += 1
        
        word_end = current_idx
        while word_end < len(text) and not text[word_end].isspace():
            word_end += 1
        
        if word_start < word_end:
            word = text[word_start:word_end]
            word_tokens = count_tokens_text(word)
            
            if current_tokens + word_tokens > max_tokens:
                return word_start  # Retourne au début du mot qui ferait dépasser
            
            current_tokens += word_tokens
            current_idx = word_end
    
    return current_idx


def _find_word_boundary(text: str, start_idx: int) -> int:
    """
    Trouve la limite d'un mot pour éviter les coupures.
    """
    idx = start_idx
    
    # Saute les espaces
    while idx < len(text) and text[idx].isspace():
        idx += 1
    
    # Si on est au début d'un mot, c'est bon
    if idx == 0 or text[idx-1].isspace():
        return idx
    
    # Sinon, trouve le début du mot actuel
    while idx > 0 and not text[idx-1].isspace():
        idx -= 1
    
    return idx


def should_chunk_response(result: Dict[str, Any], tool_name: str) -> bool:
    """
    Détermine si une réponse MCP doit être chunkée.
    
    Args:
        result: Résultat de l'outil MCP
        tool_name: Nom de l'outil
        
    Returns:
        True si chunking nécessaire
    """
    # Liste des outils qui peuvent produire des réponses volumineuses
    large_response_tools = {
        "fast_get_directory_tree",
        "fast_search_code", 
        "fast_search_files",
        "fast_read_file",
        "fast_read_multiple_files",
        "fast_list_directory",
        "fast_find_large_files"
    }
    
    if tool_name not in large_response_tools:
        return False
    
    # Vérifie si le contenu est volumineux
    content = ""
    if isinstance(result, dict):
        content = str(result.get("content", ""))
    else:
        content = str(result)
    
    total_tokens = count_tokens_text(content)
    return total_tokens > MCP_MAX_RESPONSE_TOKENS


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
        self._chunk_cache: Dict[str, Dict[str, Any]] = {}  # Cache pour les chunks
        self._tool_cache: Dict[str, Dict[str, Any]] = {}  # Cache pour les résultats d'outils
    
    async def close(self):
        """Ferme toutes les connexions HTTP."""
        await self._rpc_client.close()
    
    def _store_remaining_chunks(
        self,
        server_type: str,
        tool_name: str,
        params: Dict[str, Any],
        remaining_chunks: List[str],
        original_result: Dict[str, Any],
        execution_time_ms: float
    ) -> str:
        """
        Stocke les chunks restants pour récupération ultérieure.
        
        Args:
            server_type: Type de serveur MCP
            tool_name: Nom de l'outil
            params: Paramètres originaux
            remaining_chunks: Chunks restants à stocker
            original_result: Résultat original
            execution_time_ms: Temps d'exécution
            
        Returns:
            Clé de cache pour récupérer les chunks
        """
        import hashlib
        
        # Génère une clé unique pour cette opération chunkée
        key_data = f"{server_type}:{tool_name}:{str(params)}:{datetime.now().isoformat()}"
        cache_key = hashlib.md5(key_data.encode()).hexdigest()[:16]
        
        # Stocke les métadonnées et chunks
        self._chunk_cache[cache_key] = {
            "server_type": server_type,
            "tool_name": tool_name,
            "params": params,
            "remaining_chunks": remaining_chunks,
            "original_result": original_result,
            "execution_time_ms": execution_time_ms,
            "created_at": datetime.now().isoformat(),
            "total_chunks": len(remaining_chunks) + 1  # +1 pour le chunk déjà retourné
        }
        
        print(f"💾 [MCP CHUNK CACHE] Stocké {len(remaining_chunks)} chunks sous clé {cache_key}")
        return cache_key
    
    async def get_next_chunk(self, cache_key: str, chunk_number: int) -> Optional[MCPToolCall]:
        """
        Récupère le chunk suivant d'une opération chunkée.
        
        Args:
            cache_key: Clé de cache
            chunk_number: Numéro du chunk demandé (1-based)
            
        Returns:
            MCPToolCall avec le chunk demandé, ou None si indisponible
        """
        if cache_key not in self._chunk_cache:
            return None
        
        cache_entry = self._chunk_cache[cache_key]
        remaining_chunks = cache_entry["remaining_chunks"]
        
        # Vérifie si le chunk demandé existe
        chunk_index = chunk_number - 1  # Convertit en 0-based
        if chunk_index < 0 or chunk_index >= len(remaining_chunks):
            return None
        
        # Construit le résultat chunké
        chunked_result = cache_entry["original_result"].copy()
        chunked_result["chunked"] = True
        chunked_result["total_chunks"] = cache_entry["total_chunks"]
        chunked_result["current_chunk"] = chunk_number
        chunked_result["content"] = remaining_chunks[chunk_index]
        chunked_result["cache_key"] = cache_key
        
        # Si c'est le dernier chunk, nettoie le cache
        if chunk_index == len(remaining_chunks) - 1:
            del self._chunk_cache[cache_key]
            print(f"🧹 [MCP CHUNK CACHE] Nettoyé cache pour {cache_key}")
        
        return MCPToolCall(
            server_type=cache_entry["server_type"],
            tool_name=cache_entry["tool_name"],
            params=cache_entry["params"],
            status="success",
            result=chunked_result,
            execution_time_ms=cache_entry["execution_time_ms"]
        )
    
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
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
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
                
                if compressed_result.success and compressed_result.compressed_content:
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
            # Vérifie le cache d'abord
            cached_result = await self._get_cached_tool_result(server_type, tool_name, params)
            if cached_result:
                return cached_result
            
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
                
                # Compresse les réponses volumineuses du filesystem
                if fs_result.content and isinstance(fs_result.content, str):
                    result["content"] = await self._compress_large_response(fs_result.content)
                    
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
            
            # Met en cache le résultat si approprié
            self._cache_tool_result(server_type, tool_name, params, result, execution_time_ms)
            
            # Vérifie si la réponse doit être chunkée
            if should_chunk_response(result, tool_name):
                content_to_chunk = ""
                if isinstance(result, dict) and "content" in result:
                    content_to_chunk = str(result.get("content", ""))
                else:
                    content_to_chunk = str(result)
                
                # Chunk la réponse volumineuse
                chunks = chunk_large_response(content_to_chunk)
                
                if len(chunks) > 1:
                    # Retourne le premier chunk avec métadonnées de chunking
                    chunked_result = result.copy() if isinstance(result, dict) else {"original_result": result}
                    chunked_result["chunked"] = True
                    chunked_result["total_chunks"] = len(chunks)
                    chunked_result["current_chunk"] = 1
                    chunked_result["content"] = chunks[0]
                    
                    # Stocke les chunks restants pour récupération ultérieure
                    self._store_remaining_chunks(
                        server_type, tool_name, params, chunks[1:], 
                        result, execution_time_ms
                    )
                    
                    print(f"📦 [MCP CHUNKING] Retour chunk 1/{len(chunks)} ({len(chunks[0]):,} chars)")
                    
                    return MCPToolCall(
                        server_type=server_type,
                        tool_name=tool_name,
                        params=params,
                        status="success",
                        result=chunked_result,
                        execution_time_ms=execution_time_ms
                    )
            
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
