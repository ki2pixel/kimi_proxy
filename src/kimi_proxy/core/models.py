"""Dataclasses métier du middleware Kimi Proxy MCP."""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class TokenMetrics:
    """Métriques de tokens extraites des logs ou de l'API."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    context_length: int = 0
    tools_tokens: int = 0
    system_message_tokens: int = 0
    source: str = "logs"
    is_compile_chat: bool = False
    is_api_error: bool = False
    raw_line: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "context_length": self.context_length,
            "tools_tokens": self.tools_tokens,
            "system_message_tokens": self.system_message_tokens,
            "source": self.source,
            "is_compile_chat": self.is_compile_chat,
            "is_api_error": self.is_api_error,
        }


@dataclass
class AnalyticsSourceState:
    """État runtime d'une source analytics multi-provider."""

    source_id: str
    source_kind: str
    path: str
    available: bool = False
    healthy: bool = True
    last_error: Optional[str] = None
    last_event_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'état en dictionnaire sérialisable."""
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "path": self.path,
            "available": self.available,
            "healthy": self.healthy,
            "last_error": self.last_error,
            "last_event_at": self.last_event_at,
        }


@dataclass
class AnalyticsEvent:
    """Événement analytics normalisé entre découverte, parsing et diffusion."""

    source_id: str
    source_kind: str
    timestamp: str
    metrics: TokenMetrics
    provider: Optional[str] = None
    model: Optional[str] = None
    session_external_id: Optional[str] = None
    preview: Optional[str] = None
    severity: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'événement en dictionnaire sérialisable."""
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "provider": self.provider,
            "model": self.model,
            "session_external_id": self.session_external_id,
            "preview": self.preview,
            "severity": self.severity,
        }


@dataclass
class MCPMemoryEntry:
    """Entrée de mémoire standardisée MCP."""
    id: Optional[int] = None
    session_id: int = 0
    memory_type: str = "episodic"
    content_hash: str = ""
    content_preview: str = ""
    full_content: str = ""
    token_count: int = 0
    access_count: int = 0
    last_accessed_at: Optional[str] = None
    created_at: Optional[str] = None
    embedding_id: Optional[str] = None
    similarity_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        result = {
            "id": self.id,
            "session_id": self.session_id,
            "memory_type": self.memory_type,
            "content_hash": self.content_hash,
            "content_preview": self.content_preview,
            "token_count": self.token_count,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
            "created_at": self.created_at,
            "similarity_score": round(self.similarity_score, 4),
            "metadata": self.metadata,
        }
        if include_content:
            result["full_content"] = self.full_content
        return result


@dataclass
class MCPCompressionResult:
    """Résultat de compression MCP via serveur externe."""
    id: Optional[int] = None
    session_id: int = 0
    timestamp: Optional[str] = None
    original_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 0.0
    algorithm: str = "zlib"
    compressed_content: str = ""
    decompression_time_ms: float = 0.0
    quality_score: float = 0.0

    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        result = {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "compression_ratio": round(self.compression_ratio, 4),
            "algorithm": self.algorithm,
            "decompression_time_ms": round(self.decompression_time_ms, 2),
            "quality_score": round(self.quality_score, 2),
        }
        if include_content:
            result["compressed_content"] = self.compressed_content
        return result


@dataclass
class QdrantSearchResult:
    """Résultat de recherche sémantique Qdrant."""
    id: str = ""
    score: float = 0.0
    content_preview: str = ""
    full_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None

    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        result = {
            "id": self.id,
            "score": round(self.score, 4),
            "content_preview": self.content_preview,
            "metadata": self.metadata,
        }
        if include_content:
            result["full_content"] = self.full_content
        if self.vector:
            result["vector_dimension"] = len(self.vector)
        return result


@dataclass
class MCPCluster:
    """Cluster de mémoire sémantique."""
    id: str = ""
    center_id: str = ""
    memory_ids: List[str] = field(default_factory=list)
    centroid: Optional[List[float]] = None
    cohesion_score: float = 0.0
    topic_label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "center_id": self.center_id,
            "memory_count": len(self.memory_ids),
            "cohesion_score": round(self.cohesion_score, 4),
            "topic_label": self.topic_label,
            "vector_dimension": len(self.centroid) if self.centroid else 0,
        }


@dataclass
class MCPExternalServerStatus:
    """Statut d'un serveur MCP externe."""
    name: str = ""
    type: str = ""
    url: str = ""
    connected: bool = False
    last_check: Optional[str] = None
    latency_ms: float = 0.0
    error_count: int = 0
    capabilities: List[str] = field(default_factory=list)
    phase: str = "phase3"

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "connected": self.connected,
            "last_check": self.last_check,
            "latency_ms": round(self.latency_ms, 2),
            "error_count": self.error_count,
            "capabilities": self.capabilities,
            "phase": self.phase,
        }


@dataclass
class MCPToolCall:
    """Appel d'outil MCP intercepté."""
    id: Optional[int] = None
    session_id: int = 0
    server_type: str = ""
    tool_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    status: str = "pending"
    timestamp: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        url_map = {
            "shrimp_task_manager": "http://localhost:8002",
            "sequential_thinking": "http://localhost:8003",
            "fast_filesystem": "http://localhost:8004",
            "json_query": "http://localhost:8005",
        }
        server_url = url_map.get(self.server_type, "")

        return {
            "id": self.id,
            "session_id": self.session_id,
            "server_type": self.server_type,
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "status": self.status,
            "timestamp": self.timestamp,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "url": server_url,
        }
