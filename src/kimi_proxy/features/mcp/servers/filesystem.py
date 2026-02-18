"""
Client MCP spécialisé pour Fast Filesystem.

Gère les 25 outils d'opérations fichiers/répertoires avec sécurité workspace.
Performance: <2-10s selon l'opération.
"""
from typing import Dict, Any, Optional
from datetime import datetime

from ..base.rpc import MCPRPCClient

# Modèles imports avec TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kimi_proxy.core.models import FileSystemResult, MCPPhase4ServerStatus
    from ..base.config import MCPClientConfig


class FileSystemMCPClient:
    """
    Client spécialisé pour Fast Filesystem MCP.
    
    Supporte 25 outils:
    - Lecture: fast_read_file, fast_read_multiple_files
    - Écriture: fast_write_file, fast_large_write_file
    - Listing: fast_list_directory, fast_list_allowed_directories
    - Info: fast_get_file_info
    - Recherche: fast_search_files, fast_search_code
    - Tree: fast_get_directory_tree
    - Disk: fast_get_disk_usage, fast_find_large_files
    - Edition: fast_edit_block, fast_safe_edit, fast_edit_multiple_blocks, fast_edit_blocks, fast_extract_lines
    - Fichiers: fast_copy_file, fast_move_file, fast_delete_file, fast_batch_file_operations
    - Archives: fast_compress_files, fast_extract_archive
    - Sync: fast_sync_directories
    
    Sécurité:
    - Vérification des permissions workspace
    - Accès limité aux répertoires autorisés
    - Backup automatique avant édition
    """
    
    # Liste des outils valides pour validation
    VALID_TOOLS = [
        "fast_list_allowed_directories", "fast_read_file", "fast_read_multiple_files",
        "fast_write_file", "fast_large_write_file", "fast_list_directory", "fast_get_file_info",
        "fast_create_directory", "fast_search_files", "fast_search_code", "fast_get_directory_tree",
        "fast_get_disk_usage", "fast_find_large_files", "fast_edit_block", "fast_safe_edit",
        "fast_edit_multiple_blocks", "fast_edit_blocks", "fast_extract_lines", "fast_copy_file",
        "fast_move_file", "fast_delete_file", "fast_batch_file_operations", "fast_compress_files",
        "fast_extract_archive", "fast_sync_directories"
    ]
    
    def __init__(self, config: "MCPClientConfig", rpc_client: MCPRPCClient):
        """
        Initialise le client Fast Filesystem MCP.
        
        Args:
            config: Configuration MCP
            rpc_client: Client RPC de base
        """
        self.config = config
        self.rpc_client = rpc_client
        self._status: Optional["MCPPhase4ServerStatus"] = None
    
    async def check_status(self) -> "MCPPhase4ServerStatus":
        """
        Vérifie le statut du serveur Fast Filesystem MCP.
        
        Teste avec un appel fast_list_allowed_directories.
        
        Returns:
            Status du serveur
        """
        from kimi_proxy.core.models import MCPPhase4ServerStatus
        
        try:
            start_time = datetime.now()
            
            result = await self.rpc_client.make_rpc_call(
                server_url=self.config.fast_filesystem_url,
                method="fast_list_allowed_directories",
                params={},
                timeout_ms=2000.0,
                api_key=self.config.fast_filesystem_api_key
            )
            
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            self._status = MCPPhase4ServerStatus(
                name="fast-filesystem-mcp",
                type="fast_filesystem",
                url=self.config.fast_filesystem_url,
                connected=True,
                last_check=datetime.now().isoformat(),
                latency_ms=latency_ms,
                tools_count=len(self.VALID_TOOLS),
                capabilities=[
                    "file_operations", "directory_operations", "search",
                    "compression", "batch_operations", "workspace_security"
                ]
            )
            return self._status
            
        except Exception:
            self._status = MCPPhase4ServerStatus(
                name="fast-filesystem-mcp",
                type="fast_filesystem",
                url=self.config.fast_filesystem_url,
                connected=False,
                last_check=datetime.now().isoformat(),
                error_count=1,
                tools_count=len(self.VALID_TOOLS),
                capabilities=[]
            )
            return self._status
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> "FileSystemResult":
        """
        Appelle un outil Fast Filesystem avec validation.
        
        Args:
            tool_name: Nom de l'outil (doit être dans VALID_TOOLS)
            params: Paramètres spécifiques à l'outil
            
        Returns:
            Résultat de l'opération
            
        Example:
            >>> # Lire un fichier
            >>> result = await client.call_tool("fast_read_file", {"path": "/tmp/test.txt"})
            >>> print(result.content)
            >>> 
            >>> # Rechercher du code
            >>> results = await client.call_tool("fast_search_code", {
            ...     "path": "/src",
            ...     "pattern": "TODO.*"
            ... })
        """
        from kimi_proxy.core.models import FileSystemResult
        
        if tool_name not in self.VALID_TOOLS:
            return FileSystemResult(
                success=False,
                operation=tool_name,
                error=f"Outil invalide: {tool_name}. Outils valides: {', '.join(self.VALID_TOOLS[:5])}..."
            )
        
        try:
            result = await self.rpc_client.make_rpc_call(
                server_url=self.config.fast_filesystem_url,
                method=tool_name,
                params=params,
                timeout_ms=self.config.fast_filesystem_timeout_ms,
                api_key=self.config.fast_filesystem_api_key
            )
            
            if not result or not isinstance(result, dict):
                return FileSystemResult(
                    success=False,
                    path=params.get("path", ""),
                    operation=tool_name,
                    error="Aucune réponse du serveur"
                )
            
            return FileSystemResult(
                success=result.get("success", True),
                path=params.get("path", params.get("source", "")),
                operation=tool_name,
                content=result.get("content"),
                bytes_affected=result.get("bytes_affected", 0),
                files_affected=result.get("files_affected", [])
            )
        except Exception as e:
            return FileSystemResult(
                success=False,
                path=params.get("path", params.get("source", "")),
                operation=tool_name,
                error=str(e)
            )
    
    # Helpers communs pour simplifier l'usage
    
    async def read_file(self, path: str, line_count: Optional[int] = None) -> "FileSystemResult":
        """
        Lit un fichier via fast_read_file.
        
        Args:
            path: Chemin du fichier
            line_count: Nombre de lignes à lire (optionnel)
            
        Returns:
            Résultat avec contenu du fichier
        """
        params = {"path": path}
        if line_count:
            params["line_count"] = line_count
        
        return await self.call_tool("fast_read_file", params)
    
    async def write_file(self, path: str, content: str, append: bool = False) -> "FileSystemResult":
        """
        Écrit dans un fichier via fast_write_file.
        
        Args:
            path: Chemin du fichier
            content: Contenu à écrire
            append: True pour ajouter, False pour écraser
            
        Returns:
            Résultat de l'opération d'écriture
        """
        return await self.call_tool("fast_write_file", {
            "path": path,
            "content": content,
            "append": append
        })
    
    async def search_code(self, path: str, pattern: str, max_results: int = 50) -> "FileSystemResult":
        """
        Recherche dans le code via fast_search_code (ripgrep).
        
        Args:
            path: Répertoire à chercher
            pattern: Pattern regex
            max_results: Nombre max de résultats
            
        Returns:
            Résultat avec matches
        """
        return await self.call_tool("fast_search_code", {
            "path": path,
            "pattern": pattern,
            "max_results": max_results
        })
    
    async def list_directory(self, path: str, recursive: bool = False) -> "FileSystemResult":
        """
        Liste un répertoire via fast_list_directory.
        
        Args:
            path: Répertoire à lister
            recursive: Lister récursivement
            
        Returns:
            Résultat avec liste des fichiers/répertoires
        """
        return await self.call_tool("fast_list_directory", {
            "path": path,
            "recursive": recursive
        })
    
    def is_available(self) -> bool:
        """Vérifie si Fast Filesystem est disponible."""
        return self._status is not None and self._status.connected
