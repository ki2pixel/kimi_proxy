"""Routes API pour la mémoire MCP."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...features.mcp import get_mcp_client, get_memory_manager

router = APIRouter()


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


@router.get("/memory/stats")
async def api_get_memory_stats():
    """Retourne les statistiques globales de mémoire MCP."""
    manager = get_memory_manager()
    stats = await manager.get_memory_stats()

    return {
        "total_memory_tokens": stats.get("total_tokens", 0),
        "total_chat_tokens": 0,
        "total_tokens": stats.get("total_tokens", 0),
        "global_memory_ratio": 0.0,
        "average_session_ratio": 0.0,
        "sessions_with_memory": stats.get("distinct_sessions", 0),
        **stats,
    }


@router.get("/memory/servers")
async def api_get_mcp_server_statuses():
    """Retourne le statut de tous les serveurs MCP externes."""
    client = get_mcp_client()
    statuses = await client.get_all_server_statuses()

    return {
        "servers": [s.to_dict() for s in statuses],
        "all_connected": all(s.connected for s in statuses),
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/memory/similarity")
async def api_search_similar(request: SimilaritySearchRequest):
    """Recherche sémantique via Qdrant MCP."""
    client = get_mcp_client()

    results = await client.search_similar(
        query=request.query,
        limit=request.limit,
        score_threshold=request.score_threshold,
    )

    return {
        "query": request.query,
        "results_count": len(results),
        "results": [r.to_dict(include_content=False) for r in results],
        "qdrant_available": client.is_qdrant_available(),
    }


@router.post("/memory/compress")
async def api_compress_content(request: CompressRequest):
    """Compresse du contenu via Context Compression MCP."""
    client = get_mcp_client()

    result = await client.compress_content(
        content=request.content,
        algorithm=request.algorithm,
        target_ratio=request.target_ratio,
    )

    return {
        "original_tokens": result.original_tokens,
        "compressed_tokens": result.compressed_tokens,
        "compression_ratio": round(result.compression_ratio, 4),
        "algorithm": result.algorithm,
        "decompression_time_ms": round(result.decompression_time_ms, 2),
        "quality_score": round(result.quality_score, 2),
        "compression_available": client.is_compression_available(),
        "savings_percent": round(result.compression_ratio * 100, 1),
    }


@router.post("/memory/store")
async def api_store_memory(session_id: int, request: StoreMemoryRequest):
    """Stocke une nouvelle mémoire standardisée."""
    manager = get_memory_manager()

    entry = await manager.store_memory(
        session_id=session_id,
        content=request.content,
        memory_type=request.memory_type,
        metadata=request.metadata,
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
        "created_at": entry.created_at,
    }


@router.get("/memory/frequent")
async def api_get_frequent_memories(
    session_id: Optional[int] = None,
    min_access_count: int = 3,
    limit: int = 10,
):
    """Récupère les mémoires fréquemment utilisées depuis SQLite."""
    manager = get_memory_manager()

    entries = await manager.get_frequent_memories(
        session_id=session_id,
        min_access_count=min_access_count,
        limit=limit,
    )

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
            "last_accessed": entry.last_accessed_at,
        }
        for entry in entries
    ]


@router.post("/memory/cluster/{session_id}")
async def api_cluster_memories(session_id: int, request: ClusterRequest):
    """Clusterise les mémoires d'une session via Qdrant."""
    client = get_mcp_client()

    clusters = await client.cluster_memories(
        session_id=session_id,
        min_cluster_size=request.min_cluster_size,
    )

    return {
        "session_id": session_id,
        "cluster_count": len(clusters),
        "clusters": [c.to_dict() for c in clusters],
        "qdrant_available": client.is_qdrant_available(),
    }


@router.get("/memory/similar/{session_id}")
async def api_find_similar_to_session(
    session_id: int,
    query: Optional[str] = None,
    limit: int = 5,
):
    """Trouve les mémoires similaires à une session."""
    manager = get_memory_manager()

    if not query:
        entries = await manager.get_frequent_memories(
            session_id=session_id,
            min_access_count=0,
            limit=3,
        )
        query = " ".join(entry.content_preview for entry in entries if entry.content_preview)

    if not query:
        return {
            "session_id": session_id,
            "query": "",
            "results_count": 0,
            "results": [],
            "message": "Aucun contenu trouvé pour la session",
        }

    results = await manager.find_similar_memories(
        query=query,
        session_id=session_id,
        limit=limit,
    )

    return {
        "session_id": session_id,
        "query": query[:100] + "..." if len(query) > 100 else query,
        "results_count": len(results),
        "results": [r.to_dict(include_content=False) for r in results],
    }


@router.post("/memory/cleanup")
async def api_cleanup_old_memories(max_age_days: int = 30):
    """Nettoie les mémoires épisodiques anciennes."""
    manager = get_memory_manager()

    deleted = await manager.cleanup_old_episodic_memories(max_age_days)

    return {
        "deleted_count": deleted,
        "max_age_days": max_age_days,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/memory/promote-patterns/{session_id}")
async def api_promote_frequent_patterns(session_id: int):
    """Détecte et promeut les patterns fréquents en mémoire fréquente."""
    manager = get_memory_manager()

    promoted = await manager.detect_and_promote_frequent_patterns(session_id)

    return {
        "session_id": session_id,
        "promoted_count": promoted,
        "message": f"{promoted} mémoires promues en 'frequent'",
    }
