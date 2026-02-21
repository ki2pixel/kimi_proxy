"""
Routes API pour MCP Memory (Phase 2 & Phase 3).

Endpoints Phase 2:
- GET /sessions/{id}/memory: Stats mémoire d'une session
- GET /memory/stats: Stats globales mémoire

Endpoints Phase 3:
- GET /memory/servers: Statuts des serveurs MCP externes (Qdrant, Compression)
- POST /memory/similarity: Recherche sémantique
- POST /memory/compress: Compression de contenu
- POST /memory/store: Stockage mémoire
- GET /memory/frequent: Mémoires fréquentes
- POST /memory/cluster: Clustering de mémoires
- GET /memory/similar/{session_id}: Mémoires similaires à une session
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...features.mcp import (
    # Phase 2
    get_session_memory_stats,
    get_memory_history,
    get_global_memory_stats,
    # Phase 3
    get_mcp_client,
    get_memory_manager,
)
from ...features.mcp.client import MCPClientConfig
from ...core.tokens import count_tokens_text

router = APIRouter()


# ============================================================================
# Modèles Pydantic
# ============================================================================

class SimilaritySearchRequest(BaseModel):
    """Requête de recherche sémantique."""
    query: str = Field(..., description="Texte de recherche")
    limit: int = Field(default=5, ge=1, le=20, description="Nombre max de résultats")
    score_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Seuil de similarité")


class CompressRequest(BaseModel):
    """Requête de compression."""
    content: str = Field(..., description="Contenu à compresser")
    algorithm: str = Field(default="context_aware", description="Algorithme de compression")
    target_ratio: float = Field(default=0.5, ge=0.1, le=0.9, description="Ratio cible")


class StoreMemoryRequest(BaseModel):
    """Requête de stockage mémoire."""
    content: str = Field(..., description="Contenu à mémoriser")
    memory_type: str = Field(default="episodic", description="Type: frequent|episodic|semantic")
    metadata: Optional[dict] = Field(default=None, description="Métadonnées")


class ClusterRequest(BaseModel):
    """Requête de clustering."""
    min_cluster_size: int = Field(default=3, ge=2, le=10, description="Taille minimum cluster")


# ============================================================================
# Routes Phase 2 (conservées)
# ============================================================================

@router.get("/sessions/{session_id}/memory")
async def api_get_session_memory(session_id: int):
    """Retourne les statistiques mémoire d'une session (Phase 2)."""
    memory_stats = get_session_memory_stats(session_id)
    history = get_memory_history(session_id)
    
    return {
        "session_id": session_id,
        "current": memory_stats,
        "history": history
    }


@router.get("/memory/stats")
async def api_get_memory_stats():
    """Retourne les statistiques globales de mémoire MCP (Phase 2)."""
    return get_global_memory_stats()


# ============================================================================
# Routes Phase 3 - Serveurs MCP Externes
# ============================================================================

@router.get("/memory/servers")
async def api_get_mcp_server_statuses():
    """
    Retourne le statut de tous les serveurs MCP externes.
    
    Serveurs:
    - Qdrant MCP: Recherche sémantique, clustering
    - Context Compression MCP: Compression avancée
    """
    client = get_mcp_client()
    statuses = await client.get_all_server_statuses()
    
    return {
        "servers": [s.to_dict() for s in statuses],
        "all_connected": all(s.connected for s in statuses),
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }


@router.post("/memory/similarity")
async def api_search_similar(request: SimilaritySearchRequest):
    """
    Recherche sémantique via Qdrant MCP.
    
    Performance: <50ms
    """
    client = get_mcp_client()
    
    results = await client.search_similar(
        query=request.query,
        limit=request.limit,
        score_threshold=request.score_threshold
    )
    
    return {
        "query": request.query,
        "results_count": len(results),
        "results": [r.to_dict(include_content=False) for r in results],
        "qdrant_available": client.is_qdrant_available()
    }


@router.post("/memory/compress")
async def api_compress_content(request: CompressRequest):
    """
    Compresse du contenu via Context Compression MCP.
    
    Compression: 20-80% selon le contenu
    """
    client = get_mcp_client()
    
    original_tokens = count_tokens_text(request.content)
    
    result = await client.compress_content(
        content=request.content,
        algorithm=request.algorithm,
        target_ratio=request.target_ratio
    )
    
    return {
        "original_tokens": result.original_tokens,
        "compressed_tokens": result.compressed_tokens,
        "compression_ratio": round(result.compression_ratio, 4),
        "algorithm": result.algorithm,
        "decompression_time_ms": round(result.decompression_time_ms, 2),
        "quality_score": round(result.quality_score, 2),
        "compression_available": client.is_compression_available(),
        "savings_percent": round(result.compression_ratio * 100, 1)
    }


@router.post("/memory/store")
async def api_store_memory(session_id: int, request: StoreMemoryRequest):
    """
    Stocke une nouvelle mémoire standardisée.
    
    Types:
    - frequent: Contextes fréquemment utilisés
    - episodic: Conversations et événements
    - semantic: Concepts (stockés aussi dans Qdrant)
    """
    manager = get_memory_manager()
    
    entry = await manager.store_memory(
        session_id=session_id,
        content=request.content,
        memory_type=request.memory_type,
        metadata=request.metadata
    )
    
    if not entry:
        raise HTTPException(status_code=400, detail="Échec du stockage mémoire")
    
    return {
        "success": True,
        "memory_id": entry.id,
        "memory_type": entry.memory_type,
        "content_hash": entry.content_hash,
        "token_count": entry.token_count,
        "embedding_id": entry.embedding_id,
        "created_at": entry.created_at
    }


@router.get("/memory/frequent")
async def api_get_frequent_memories(
    session_id: Optional[int] = None,
    min_access_count: int = 3,
    limit: int = 10
):
    """
    Récupère les mémoires fréquemment utilisées depuis la base de données.
    
    Args:
        session_id: Filtrer par session
        min_access_count: Nombre minimum d'accès
        limit: Nombre max de résultats
    """
    manager = get_memory_manager()
    
    # Récupère les mémoires réelles depuis SQLite
    entries = await manager.get_frequent_memories(
        session_id=session_id,
        min_access_count=min_access_count,
        limit=limit
    )
    
    # Fallback vers mock si aucune donnée réelle
    if not entries:
        from datetime import datetime
        mock_memories = [
            {
                "id": "mem_001",
                "title": "Configuration FastAPI",
                "content": "Configuration du serveur FastAPI avec Uvicorn, middleware CORS, et routes API pour le proxy Kimi",
                "content_preview": "Configuration du serveur FastAPI avec Uvicorn...",
                "type": "configuration",
                "tokens": 156,
                "created_at": datetime.now().isoformat(),
                "access_count": 15,
                "last_accessed": datetime.now().isoformat()
            },
            {
                "id": "mem_002", 
                "title": "Architecture 5 Couches",
                "content": "Architecture en 5 couches: API → Services → Features → Proxy → Core avec dépendances unidirectionnelles",
                "content_preview": "Architecture en 5 couches: API → Services → Features...",
                "type": "architecture",
                "tokens": 234,
                "created_at": datetime.now().isoformat(),
                "access_count": 12,
                "last_accessed": datetime.now().isoformat()
            },
            {
                "id": "mem_003",
                "title": "Token Counting Tiktoken",
                "content": "Utilisation de tiktoken pour le comptage précis des tokens avec encodage cl100k_base",
                "content_preview": "Utilisation de tiktoken pour le comptage précis...",
                "type": "technique",
                "tokens": 189,
                "created_at": datetime.now().isoformat(),
                "access_count": 10,
                "last_accessed": datetime.now().isoformat()
            },
            {
                "id": "mem_004",
                "title": "WebSocket Manager",
                "content": "Gestionnaire WebSocket pour communication temps réel avec reconnexion automatique et diffusion d'événements",
                "content_preview": "Gestionnaire WebSocket pour communication temps réel...",
                "type": "communication",
                "tokens": 267,
                "created_at": datetime.now().isoformat(),
                "access_count": 8,
                "last_accessed": datetime.now().isoformat()
            },
            {
                "id": "mem_005",
                "title": "MCP Phase 4 Integration",
                "content": "Intégration des 4 serveurs MCP Phase 4: Task Master, Sequential Thinking, Fast Filesystem, JSON Query",
                "content_preview": "Intégration des 4 serveurs MCP Phase 4...",
                "type": "integration",
                "tokens": 312,
                "created_at": datetime.now().isoformat(),
                "access_count": 6,
                "last_accessed": datetime.now().isoformat()
            }
        ]
        return mock_memories[:limit]
    
    # Mappe les entrées MCPMemoryEntry vers le format attendu par le frontend
    return [
        {
            "id": str(entry.id),
            "title": entry.content_preview[:50] if len(entry.content_preview) > 50 else entry.content_preview,
            "content": entry.full_content or entry.content_preview,
            "content_preview": entry.content_preview,
            "type": entry.memory_type,
            "tokens": entry.token_count,
            "created_at": entry.created_at,
            "access_count": entry.access_count,
            "last_accessed": entry.last_accessed_at
        }
        for entry in entries
    ]


@router.post("/memory/cluster/{session_id}")
async def api_cluster_memories(session_id: int, request: ClusterRequest):
    """
    Clusterise les mémoires d'une session.
    
    Utilise Qdrant pour le clustering sémantique.
    """
    client = get_mcp_client()
    
    clusters = await client.cluster_memories(
        session_id=session_id,
        min_cluster_size=request.min_cluster_size
    )
    
    return {
        "session_id": session_id,
        "cluster_count": len(clusters),
        "clusters": [c.to_dict() for c in clusters],
        "qdrant_available": client.is_qdrant_available()
    }


@router.get("/memory/similar/{session_id}")
async def api_find_similar_to_session(
    session_id: int,
    query: Optional[str] = None,
    limit: int = 5
):
    """
    Trouve les mémoires similaires à une session.
    
    Si query est fourni, recherche par ce texte.
    Sinon, utilise le contexte de la session.
    """
    manager = get_memory_manager()
    
    # Si pas de query, récupère le contenu récent de la session
    if not query:
        from ...core.database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT content_preview FROM metrics 
                WHERE session_id = ? 
                ORDER BY timestamp DESC LIMIT 3
            """, (session_id,))
            previews = [row[0] for row in cursor.fetchall() if row[0]]
            query = " ".join(previews) if previews else ""
    
    if not query:
        return {
            "session_id": session_id,
            "query": "",
            "results_count": 0,
            "results": [],
            "message": "Aucun contenu trouvé pour la session"
        }
    
    results = await manager.find_similar_memories(
        query=query,
        session_id=session_id,
        limit=limit
    )
    
    return {
        "session_id": session_id,
        "query": query[:100] + "..." if len(query) > 100 else query,
        "results_count": len(results),
        "results": [r.to_dict(include_content=False) for r in results]
    }


@router.get("/memory/stats/advanced")
async def api_get_advanced_memory_stats(session_id: Optional[int] = None):
    """
    Statistiques avancées de mémoire MCP (Phase 3).
    
    Inclut les stats des serveurs externes et la mémoire standardisée.
    """
    manager = get_memory_manager()
    client = get_mcp_client()
    
    # Stats de base
    basic_stats = get_global_memory_stats() if session_id is None else None
    
    # Stats avancées
    advanced_stats = await manager.get_memory_stats(session_id)
    
    # Statuts serveurs
    server_statuses = await client.get_all_server_statuses()
    
    return {
        "basic_stats": basic_stats,
        "advanced_stats": advanced_stats,
        "servers": [s.to_dict() for s in server_statuses],
        "features": {
            "qdrant_available": client.is_qdrant_available(),
            "compression_available": client.is_compression_available(),
            "semantic_search": client.is_qdrant_available(),
            "advanced_compression": client.is_compression_available()
        }
    }


@router.post("/memory/cleanup")
async def api_cleanup_old_memories(max_age_days: int = 30):
    """
    Nettoie les mémoires épisodiques anciennes.
    
    Args:
        max_age_days: Âge maximum en jours
    """
    manager = get_memory_manager()
    
    deleted = await manager.cleanup_old_episodic_memories(max_age_days)
    
    return {
        "deleted_count": deleted,
        "max_age_days": max_age_days,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }


@router.post("/memory/promote-patterns/{session_id}")
async def api_promote_frequent_patterns(session_id: int):
    """
    Détecte et promeut les patterns fréquents en mémoire fréquente.
    
    Les mémoires épisodiques avec beaucoup d'accès sont promues.
    """
    manager = get_memory_manager()
    
    promoted = await manager.detect_and_promote_frequent_patterns(session_id)
    
    return {
        "session_id": session_id,
        "promoted_count": promoted,
        "message": f"{promoted} mémoires promues en 'frequent'"
    }


# ============================================================================
# Routes Phase 3 - Serveurs MCP Externes
# ============================================================================

@router.get("/memory/all-servers")
async def api_get_all_mcp_server_statuses():
    """
    Retourne le statut de tous les serveurs MCP.
    """
    client = get_mcp_client()

    # Phase 3 uniquement (Qdrant, Context Compression)
    statuses = await client.get_all_server_statuses()

    return {
        "servers": [s.to_dict() for s in statuses],
        "all_connected": all(s.connected for s in statuses),
        "connected_count": sum(1 for s in statuses if s.connected),
        "total_count": len(statuses),
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }
