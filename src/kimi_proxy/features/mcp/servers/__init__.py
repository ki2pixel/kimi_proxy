"""
Package des clients MCP spécialisés par serveur.

Ce package contient des clients dédiés pour chaque serveur MCP:
- qdrant: Recherche sémantique et clustering
- compression: Compression contextuelle
- task_master: Gestion de tâches
- sequential: Raisonnement séquentiel
- filesystem: Opérations fichiers
- json_query: Requêtes JSON
"""

from .qdrant import QdrantMCPClient
from .compression import CompressionMCPClient
from .task_master import TaskMasterMCPClient
from .sequential import SequentialThinkingMCPClient
from .filesystem import FileSystemMCPClient
from .json_query import JsonQueryMCPClient

__all__ = [
    "QdrantMCPClient",
    "CompressionMCPClient",
    "TaskMasterMCPClient",
    "SequentialThinkingMCPClient",
    "FileSystemMCPClient",
    "JsonQueryMCPClient",
]
