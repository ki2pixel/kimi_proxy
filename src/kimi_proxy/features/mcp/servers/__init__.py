"""
Package des clients MCP spécialisés par serveur.

Ce package contient des clients dédiés pour chaque serveur MCP:
- qdrant: Recherche sémantique et clustering
- compression: Compression contextuelle
"""

from .qdrant import QdrantMCPClient
from .compression import CompressionMCPClient

__all__ = [
    "QdrantMCPClient",
    "CompressionMCPClient",
]
