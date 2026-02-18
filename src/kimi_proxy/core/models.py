"""
Dataclasses métier pour Kimi Proxy Dashboard.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class Session:
    """Représente une session de monitoring."""
    id: int
    name: str
    provider: str = "managed:kimi-code"
    model: Optional[str] = None
    created_at: Optional[str] = None
    is_active: bool = False
    # Phase 1 Context Compaction
    reserved_tokens: int = 0
    compaction_count: int = 0
    last_compaction_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la session en dictionnaire."""
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at,
            "is_active": self.is_active,
            "reserved_tokens": self.reserved_tokens,
            "compaction_count": self.compaction_count,
            "last_compaction_at": self.last_compaction_at
        }


@dataclass
class Metric:
    """Représente une métrique de tokens."""
    id: int
    session_id: int
    timestamp: str
    estimated_tokens: int
    percentage: float
    content_preview: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    is_estimated: bool = True
    source: str = "proxy"
    memory_tokens: int = 0
    chat_tokens: int = 0
    memory_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la métrique en dictionnaire."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "estimated_tokens": self.estimated_tokens,
            "percentage": self.percentage,
            "content_preview": self.content_preview,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "is_estimated": self.is_estimated,
            "source": self.source,
            "memory_tokens": self.memory_tokens,
            "chat_tokens": self.chat_tokens,
            "memory_ratio": self.memory_ratio
        }


@dataclass
class Provider:
    """Configuration d'un provider LLM."""
    key: str
    name: str
    type: str  # "openai", "gemini", "kimi"
    base_url: str
    api_key: Optional[str] = None
    models: List[str] = field(default_factory=list)
    
    def to_dict(self, mask_api_key: bool = True) -> Dict[str, Any]:
        """Convertit le provider en dictionnaire."""
        return {
            "key": self.key,
            "name": self.name,
            "type": self.type,
            "base_url": self.base_url,
            "api_key": "***" if mask_api_key and self.api_key else self.api_key,
            "models": self.models
        }


@dataclass
class Model:
    """Configuration d'un modèle LLM."""
    key: str
    model: str
    provider: str
    max_context_size: int = 262144
    capabilities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le modèle en dictionnaire."""
        return {
            "key": self.key,
            "model": self.model,
            "provider": self.provider,
            "max_context_size": self.max_context_size,
            "capabilities": self.capabilities
        }


@dataclass
class MaskedContent:
    """Contenu masqué par le sanitizer."""
    id: Optional[int] = None
    content_hash: str = ""
    original_content: str = ""
    preview: str = ""
    file_path: str = ""
    tags: List[str] = field(default_factory=list)
    token_count: int = 0
    created_at: Optional[str] = None
    
    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        result = {
            "id": self.id,
            "hash": self.content_hash,
            "preview": self.preview,
            "tags": self.tags,
            "token_count": self.token_count,
            "created_at": self.created_at,
            "file_path": self.file_path
        }
        if include_content:
            result["original_content"] = self.original_content
        return result


@dataclass
class MemoryMetrics:
    """Métriques de mémoire MCP pour une session."""
    id: Optional[int] = None
    session_id: int = 0
    timestamp: Optional[str] = None
    memory_tokens: int = 0
    chat_tokens: int = 0
    memory_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "memory_tokens": self.memory_tokens,
            "chat_tokens": self.chat_tokens,
            "memory_ratio": self.memory_ratio
        }


@dataclass
class MemorySegment:
    """Segment de mémoire individuel détecté."""
    id: Optional[int] = None
    session_id: int = 0
    metric_id: Optional[int] = None
    segment_type: str = ""
    content_preview: str = ""
    token_count: int = 0
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "metric_id": self.metric_id,
            "type": self.segment_type,
            "preview": self.content_preview,
            "token_count": self.token_count,
            "created_at": self.created_at
        }


@dataclass
class CompressionLog:
    """Log de compression d'historique."""
    id: Optional[int] = None
    session_id: int = 0
    timestamp: Optional[str] = None
    original_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 0.0
    summary_preview: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "compression_ratio": self.compression_ratio,
            "summary_preview": self.summary_preview
        }


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
            "is_api_error": self.is_api_error
        }


@dataclass
class CompactionHistoryEntry:
    """Entrée d'historique de compaction."""
    id: Optional[int] = None
    session_id: int = 0
    timestamp: Optional[str] = None
    tokens_before: int = 0
    tokens_after: int = 0
    tokens_saved: int = 0
    preserved_messages: int = 0
    summarized_messages: int = 0
    compaction_ratio: float = 0.0
    trigger_reason: str = "manual"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "tokens_before": self.tokens_before,
            "tokens_after": self.tokens_after,
            "tokens_saved": self.tokens_saved,
            "preserved_messages": self.preserved_messages,
            "summarized_messages": self.summarized_messages,
            "compaction_ratio": self.compaction_ratio,
            "trigger_reason": self.trigger_reason
        }


# ============================================================================
# MCP PHASE 3 - Mémoire Avancée et Routage Optimisé
# ============================================================================

@dataclass
class MCPMemoryEntry:
    """Entrée de mémoire standardisée MCP (Phase 3)."""
    id: Optional[int] = None
    session_id: int = 0
    memory_type: str = "episodic"  # "frequent" | "episodic" | "semantic"
    content_hash: str = ""
    content_preview: str = ""
    full_content: str = ""
    token_count: int = 0
    access_count: int = 0
    last_accessed_at: Optional[str] = None
    created_at: Optional[str] = None
    embedding_id: Optional[str] = None  # Référence Qdrant
    similarity_score: float = 0.0  # Score de similarité (0-1)
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
            "metadata": self.metadata
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
    algorithm: str = "zlib"  # "zlib" | "context-compression-mcp"
    compressed_content: str = ""
    decompression_time_ms: float = 0.0
    quality_score: float = 0.0  # Score de qualité de compression (0-1)
    
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
            "quality_score": round(self.quality_score, 2)
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
            "metadata": self.metadata
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
            "vector_dimension": len(self.centroid) if self.centroid else 0
        }


@dataclass
class ProviderRoutingDecision:
    """Décision de routage provider basée sur capacité contexte."""
    original_provider: str = ""
    selected_provider: str = ""
    original_model: str = ""
    selected_model: str = ""
    required_context: int = 0
    available_context: int = 0
    context_remaining: int = 0
    confidence_score: float = 0.0
    reason: str = ""
    fallback_triggered: bool = False
    estimated_cost: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "original_provider": self.original_provider,
            "selected_provider": self.selected_provider,
            "original_model": self.original_model,
            "selected_model": self.selected_model,
            "required_context": self.required_context,
            "available_context": self.available_context,
            "context_remaining": self.context_remaining,
            "confidence_score": round(self.confidence_score, 4),
            "reason": self.reason,
            "fallback_triggered": self.fallback_triggered,
            "estimated_cost": round(self.estimated_cost, 4)
        }


@dataclass
class MCPExternalServerStatus:
    """Statut d'un serveur MCP externe (Phase 3)."""
    name: str = ""
    type: str = ""  # "qdrant" | "context-compression"
    url: str = ""
    connected: bool = False
    last_check: Optional[str] = None
    latency_ms: float = 0.0
    error_count: int = 0
    capabilities: List[str] = field(default_factory=list)
    phase: str = "phase3"  # Pour distinction UI Phase 3 vs Phase 4
    
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
            "phase": self.phase
        }


@dataclass
class StatusSnapshot:
    """Snapshot complet du statut pour le dashboard."""
    session_id: int
    total_tokens: int = 0
    max_context: int = 262144
    percentage: float = 0.0
    reserved_tokens: int = 0
    context_usage_reserved: float = 0.0  # Pourcentage avec réservation
    compaction_ready: bool = False  # True si compaction recommandée
    compaction_count: int = 0
    last_compaction_at: Optional[str] = None
    alert_level: Optional[str] = None  # caution, warning, critical
    provider: str = "managed:kimi-code"
    model: Optional[str] = None
    timestamp: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "session_id": self.session_id,
            "total_tokens": self.total_tokens,
            "max_context": self.max_context,
            "percentage": round(self.percentage, 2),
            "reserved_tokens": self.reserved_tokens,
            "context_usage_reserved": round(self.context_usage_reserved, 2),
            "compaction_ready": self.compaction_ready,
            "compaction_count": self.compaction_count,
            "last_compaction_at": self.last_compaction_at,
            "alert_level": self.alert_level,
            "provider": self.provider,
            "model": self.model,
            "timestamp": self.timestamp
        }


# ============================================================================
# MCP PHASE 4 - Modèles pour les nouveaux serveurs MCP
# ============================================================================

@dataclass
class TaskMasterTask:
    """Tâche Task Master."""
    id: str = ""
    title: str = ""
    description: str = ""
    status: str = "pending"  # pending, in-progress, done, blocked, deferred
    priority: str = "medium"  # high, medium, low
    dependencies: List[str] = field(default_factory=list)
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "subtasks": self.subtasks,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class TaskMasterStats:
    """Statistiques Task Master."""
    total_tasks: int = 0
    pending: int = 0
    in_progress: int = 0
    done: int = 0
    blocked: int = 0
    deferred: int = 0
    total_complexity_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "total_tasks": self.total_tasks,
            "pending": self.pending,
            "in_progress": self.in_progress,
            "done": self.done,
            "blocked": self.blocked,
            "deferred": self.deferred,
            "total_complexity_score": round(self.total_complexity_score, 2)
        }


@dataclass
class SequentialThinkingStep:
    """Étape de raisonnement séquentiel."""
    step_number: int = 0
    thought: str = ""
    next_thought_needed: bool = False
    total_thoughts: int = 0
    branches: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "step_number": self.step_number,
            "thought": self.thought,
            "next_thought_needed": self.next_thought_needed,
            "total_thoughts": self.total_thoughts,
            "branches": self.branches,
            "url": "http://localhost:8003"  # Champ requis par Continue.dev pour Sequential Thinking
        }


@dataclass
class FileSystemResult:
    """Résultat d'opération filesystem."""
    success: bool = False
    path: str = ""
    operation: str = ""
    content: Optional[str] = None
    error: Optional[str] = None
    bytes_affected: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        result = {
            "success": self.success,
            "path": self.path,
            "operation": self.operation,
            "error": self.error,
            "bytes_affected": self.bytes_affected
        }
        if self.content is not None:
            result["content"] = self.content[:500] + "..." if len(self.content) > 500 else self.content
        return result


@dataclass
class JsonQueryResult:
    """Résultat de requête JSON."""
    success: bool = False
    query: str = ""
    file_path: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "success": self.success,
            "query": self.query,
            "file_path": self.file_path,
            "results_count": len(self.results),
            "results": self.results[:10] if len(self.results) > 10 else self.results,  # Limite pour la taille
            "error": self.error,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "url": "http://localhost:8005"  # Champ requis par Continue.dev pour JSON Query
        }


@dataclass
class MCPToolCall:
    """Appel d'outil MCP intercepté."""
    id: Optional[int] = None
    session_id: int = 0
    server_type: str = ""  # task_master, sequential_thinking, fast_filesystem, json_query
    tool_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, success, error
    timestamp: Optional[str] = None
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        # Déterminer l'URL du serveur basé sur le type
        url_map = {
            "task_master": "http://localhost:8002",
            "sequential_thinking": "http://localhost:8003", 
            "fast_filesystem": "http://localhost:8004",
            "json_query": "http://localhost:8005"
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
            "url": server_url  # Champ requis par Continue.dev
        }


@dataclass
class MCPPhase4ServerStatus:
    """Statut d'un serveur MCP Phase 4."""
    name: str = ""
    type: str = ""  # task_master, sequential_thinking, fast_filesystem, json_query
    url: str = ""
    connected: bool = False
    last_check: Optional[str] = None
    latency_ms: float = 0.0
    error_count: int = 0
    tools_count: int = 0
    capabilities: List[str] = field(default_factory=list)
    phase: str = "phase4"  # Pour distinction UI Phase 3 vs Phase 4
    
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
            "tools_count": self.tools_count,
            "capabilities": self.capabilities,
            "phase": self.phase,
            "tool_count": self.tools_count  # Alias pour compatibilité frontend
        }
