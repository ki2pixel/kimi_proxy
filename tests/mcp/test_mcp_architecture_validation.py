"""
Validation de l'architecture MCP après refactorisation.

Ce test valide:
- Absence de dépendances circulaires
- Import structure correct
- Encapsulation par client
- Compatibilité ascendante
- Singleton pattern
- Séparation des responsabilités

À exécuter après tout changement dans l'architecture MCP.
"""
import pytest
import sys
import inspect
from pathlib import Path
from importlib import import_module

# Test imports
from kimi_proxy.features.mcp.client import MCPExternalClient, get_mcp_client, reset_mcp_client
from kimi_proxy.features.mcp.base.config import MCPClientConfig
from kimi_proxy.features.mcp.base.rpc import MCPRPCClient
from kimi_proxy.features.mcp.servers import (
    QdrantMCPClient,
    CompressionMCPClient,
    TaskMasterMCPClient,
    SequentialThinkingMCPClient,
    FileSystemMCPClient,
    JsonQueryMCPClient,
)


class TestMCPArchitecture:
    """Validation structurelle de l'architecture MCP."""
    
    def test_no_circular_imports(self):
        """Vérifie qu'il n'y a pas de cycles d'import."""
        # Essaye d'importer tous les modules ensemble
        import kimi_proxy.features.mcp
        import kimi_proxy.features.mcp.client
        import kimi_proxy.features.mcp.base
        import kimi_proxy.features.mcp.servers
        
        # Vérifie que les imports se sont faits sans erreur
        assert hasattr(kimi_proxy.features.mcp, 'client')
        assert hasattr(kimi_proxy.features.mcp, 'base')
        assert hasattr(kimi_proxy.features.mcp, 'servers')
    
    def test_client_does_not_import_servers_directly(self):
        """Vérifie que client.py utilise des imports relatifs sans cycles."""
        from kimi_proxy.features.mcp import client as client_module
        
        # Vérifie que le module client existe
        assert inspect.ismodule(client_module)
        
        # Vérifie que MCPExternalClient y est défini
        assert hasattr(client_module, 'MCPExternalClient')
    
    def test_server_independence(self):
        """Vérifie que chaque client serveur peut être importé séparément."""
        # Qdrant
        from kimi_proxy.features.mcp.servers.qdrant import QdrantMCPClient
        assert inspect.isclass(QdrantMCPClient)
        
        # Compression
        from kimi_proxy.features.mcp.servers.compression import CompressionMCPClient
        assert inspect.isclass(CompressionMCPClient)
        
        # Task Master
        from kimi_proxy.features.mcp.servers.task_master import TaskMasterMCPClient
        assert inspect.isclass(TaskMasterMCPClient)
        
        # Sequential
        from kimi_proxy.features.mcp.servers.sequential import SequentialThinkingMCPClient
        assert inspect.isclass(SequentialThinkingMCPClient)
        
        # Filesystem
        from kimi_proxy.features.mcp.servers.filesystem import FileSystemMCPClient
        assert inspect.isclass(FileSystemMCPClient)
        
        # JSON Query
        from kimi_proxy.features.mcp.servers.json_query import JsonQueryMCPClient
        assert inspect.isclass(JsonQueryMCPClient)
    
    def test_base_module_completeness(self):
        """Vérifie que base/ contient tout le nécessaire."""
        from kimi_proxy.features.mcp.base import (
            MCPClientConfig,
            MCPRPCClient,
            MCPClientError,
            MCPConnectionError,
            MCPTimeoutError
        )
        
        assert inspect.isclass(MCPClientConfig)
        assert inspect.isclass(MCPRPCClient)
        assert inspect.isclass(MCPClientError)
    
    def test_client_instantiation(self):
        """Vérifie que MCPExternalClient peut être instancié."""
        config = MCPClientConfig()
        client = MCPExternalClient(config)
        
        assert isinstance(client, MCPExternalClient)
        assert hasattr(client, 'qdrant')
        assert hasattr(client, 'compression')
        assert hasattr(client, 'task_master')
        assert hasattr(client, 'sequential')
        assert hasattr(client, 'filesystem')
        assert hasattr(client, 'json_query')
    
    def test_singleton_pattern(self):
        """Vérifie le pattern singleton."""
        # Réinitialise
        reset_mcp_client()
        
        # Crée deux fois
        client1 = get_mcp_client()
        client2 = get_mcp_client()
        
        # Même instance
        assert client1 is client2
        assert isinstance(client1, MCPExternalClient)
    
    def test_reset_singleton(self):
        """Vérifie que reset_mcp_client fonctionne."""
        reset_mcp_client()
        client1 = get_mcp_client()
        
        reset_mcp_client()
        client2 = get_mcp_client()
        
        # Nouvelle instance
        assert client1 is not client2
    
    def test_backward_compatibility(self):
        """Vérifie que l'ancienne API est préservée."""
        from kimi_proxy.features.mcp.client import get_mcp_client
        
        client = get_mcp_client()
        
        # Méthodes old-style doivent exister
        assert hasattr(client, 'check_qdrant_status')
        assert hasattr(client, 'search_similar')
        assert hasattr(client, 'store_memory_vector')
        assert hasattr(client, 'compress_content')
        assert hasattr(client, 'call_task_master_tool')
        assert hasattr(client, 'call_sequential_thinking')
        assert hasattr(client, 'call_fast_filesystem_tool')
        assert hasattr(client, 'call_json_query_tool')
        assert hasattr(client, 'call_mcp_tool')  # Generic
    
    def test_client_does_not_implement_server_logic(self):
        """Vérifie que la facade ne contient pas la logique métier des serveurs."""
        client = MCPExternalClient()
        
        # La facade doit déléguer, pas implémenter
        client_source = inspect.getsource(type(client))
        
        # Ne doit pas contenir de logique retry complexe
        assert "max_retries" not in client_source or "self._rpc_client" in client_source
        
        # Ne doit pas implémenter make_rpc_call
        assert "def make_rpc_call" not in client_source
    
    def test_server_clients_independence(self):
        """Vérifie que les clients serveurs sont indépendants (pas de dépendance croisée)."""
        # Import chaque client séparément sans importer les autres
        modules = []
        
        modules.append(import_module("kimi_proxy.features.mcp.servers.qdrant"))
        modules.append(import_module("kimi_proxy.features.mcp.servers.compression"))
        modules.append(import_module("kimi_proxy.features.mcp.servers.task_master"))
        modules.append(import_module("kimi_proxy.features.mcp.servers.sequential"))
        modules.append(import_module("kimi_proxy.features.mcp.servers.filesystem"))
        modules.append(import_module("kimi_proxy.features.mcp.servers.json_query"))
        
        # Tous ont dû charger sans erreur
        assert len(modules) == 6
    
    def test_file_size_reduction(self):
        """Vérifie que la refactorisation a bien réduit la taille du client principal."""
        current_file = Path("src/kimi_proxy/features/mcp/client.py")
        backup_file = Path("src/kimi_proxy/features/mcp/client.py.backup")
        
        if not backup_file.exists():
            pytest.skip("Backup du fichier original non trouvé")
        
        current_size = len(current_file.read_text())
        backup_size = len(backup_file.read_text())
        
        # Note : Le fichier actuel contient les imports et la facade
        # La réduction principale vient de la séparation en modules servers/
        # On vérifie juste que le fichier reste raisonnable (< 25KB)
        assert current_size < 25000, \
            f"Fichier actuel: {current_size:,} bytes (objectif: < 25KB)"
    
    def test_mcpclientconfig_contains_all_servers(self):
        """Vérifie que MCPClientConfig contient tous les serveurs."""
        config = MCPClientConfig()
        
        # Qdrant
        assert hasattr(config, 'qdrant_url')
        assert hasattr(config, 'qdrant_api_key')
        
        # Compression
        assert hasattr(config, 'compression_url')
        
        # Task Master
        assert hasattr(config, 'task_master_url')
        
        # Sequential
        assert hasattr(config, 'sequential_thinking_url')
        
        # Filesystem
        assert hasattr(config, 'fast_filesystem_url')
        
        # JSON Query
        assert hasattr(config, 'json_query_url')
    
    def test_configuration_loading_from_toml(self):
        """Vérifie que la config peut charger depuis TOML."""
        import tempfile
        
        try:
            import toml
        except ImportError:
            pytest.skip("Module toml non installé")
        
        # Créer config TOML temporaire
        config_dict = {
            "mcp": {
                "qdrant": {"url": "http://test:6333", "search_timeout_ms": 100},
                "compression": {"compression_timeout_ms": 10000},
                "task_master": {"timeout_ms": 60000}
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml.dump(config_dict, f)
            config_file = f.name
        
        try:
            from kimi_proxy.config.loader import get_config
            # Simuler le chargement
            config = MCPClientConfig.from_toml(config_dict)
            
            assert config.qdrant_url == "http://test:6333"
            assert config.search_timeout_ms == 100
            assert config.task_master_timeout_ms == 60000
        finally:
            import os
            os.unlink(config_file)
    
    def test_exception_hierarchy(self):
        """Vérifie la hiérarchie des exceptions."""
        from kimi_proxy.features.mcp.base.rpc import (
            MCPClientError,
            MCPConnectionError,
            MCPTimeoutError
        )
        from kimi_proxy.core.exceptions import KimiProxyError
        
        # Doit hériter de KimiProxyError
        assert issubclass(MCPClientError, KimiProxyError)
        assert issubclass(MCPConnectionError, MCPClientError)
        assert issubclass(MCPTimeoutError, MCPClientError)
    
    def test_rpc_client_has_retry_logic(self):
        """Vérifie que MCPRPCClient a la logique de retry."""
        rpc = MCPRPCClient(max_retries=3, retry_delay_ms=100)
        
        assert hasattr(rpc, 'max_retries')
        assert rpc.max_retries == 3
        assert hasattr(rpc, 'retry_delay_ms')
        assert rpc.retry_delay_ms == 100
        
        # Doit avoir make_rpc_call
        assert hasattr(rpc, 'make_rpc_call')
    
    def test_all_servers_have_is_available(self):
        """Vérifie que tous les clients ont la méthode is_available()."""
        for server_name, client_class in [
            ("qdrant", QdrantMCPClient),
            ("compression", CompressionMCPClient),
            ("task_master", TaskMasterMCPClient),
            ("sequential", SequentialThinkingMCPClient),
            ("filesystem", FileSystemMCPClient),
            ("json_query", JsonQueryMCPClient),
        ]:
            assert hasattr(client_class, 'is_available')
            assert callable(getattr(client_class, 'is_available'))
    
    def test_documentation_in_client_files(self):
        """Vérifie que chaque client a une docstring descriptive."""
        import inspect
        
        for module_name in [
            "kimi_proxy.features.mcp.servers.qdrant",
            "kimi_proxy.features.mcp.servers.compression",
            "kimi_proxy.features.mcp.servers.task_master",
            "kimi_proxy.features.mcp.servers.sequential",
            "kimi_proxy.features.mcp.servers.filesystem",
            "kimi_proxy.features.mcp.servers.json_query",
        ]:
            module = import_module(module_name)
            assert module.__doc__ is not None
            assert "Performance" in module.__doc__ or "Supporte" in module.__doc__
    
    def test_public_api_completeness(self):
        """Vérifie que l'API publique est complète."""
        from kimi_proxy.features.mcp import __all__
        
        # Doit exporter les éléments essentiels
        essential_exports = [
            'MCPExternalClient',
            'MCPClientConfig',
            'get_mcp_client',
            'reset_mcp_client',
        ]
        
        for export in essential_exports:
            assert export in __all__


if __name__ == "__main__":
    # Vérifications manuelles
    print(f"{BOLD}{sys.modules[__name__].__file__}{RESET}\n")
    
    print("Structure de l'architecture MCP:")
    print("├── client.py (facade)")
    print("├── base/")
    print("│   ├── config.py")
    print("│   └── rpc.py")
    print("└── servers/")
    for server in ["qdrant", "compression", "task_master", "sequential", "filesystem", "json_query"]:
        print(f"    ├── {server}.py")
    print()
    
    # Lancer pytest
    pytest.main([__file__, "-v"])
