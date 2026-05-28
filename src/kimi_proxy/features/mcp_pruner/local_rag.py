"""kimi_proxy.features.mcp_pruner.local_rag

Moteur de pruning local s'appuyant sur sentence-transformers et un VectorStore NumPy.
Chargement paresseux (lazy) des dépendances pour préserver l'aspect lightweight de Kimi Proxy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal, Any

from kimi_proxy.core.tokens import count_tokens_text


class EmbeddingModel:
    """Chargeur lazy du modèle d'embeddings sentence-transformers."""
    _instances: dict[str, "EmbeddingModel"] = {}

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2"):
        if model_name in cls._instances:
            return cls._instances[model_name]
        instance = super().__new__(cls)
        instance._model_name = model_name
        instance._model = None
        cls._instances[model_name] = instance
        return instance

    def _load(self) -> None:
        if self._model is None:
            # Import paresseux pour ne pas ralentir le démarrage si inutilisé
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)

    def embed(self, texts: list[str]) -> Any: # Returns np.ndarray
        self._load()
        return self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def embed_single(self, text: str) -> Any: # Returns np.ndarray
        return self.embed([text])[0]


@dataclass
class SearchResult:
    index: int
    score: float
    document: str


class VectorStore:
    """Store vectoriel NumPy en mémoire avec recherche de similarité cosinus."""
    def __init__(self):
        self._embeddings: Any | None = None # np.ndarray
        self._documents: list[str] = []

    @property
    def size(self) -> int:
        return len(self._documents)

    def add(self, embeddings: Any, documents: list[str]) -> None:
        import numpy as np
        if len(embeddings) != len(documents):
            raise ValueError(f"Mismatch: {len(embeddings)} embeddings vs {len(documents)} documents")
        
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        normed_embeddings = embeddings / norms
        
        if self._embeddings is None:
            self._embeddings = normed_embeddings.copy()
        else:
            self._embeddings = np.vstack([self._embeddings, normed_embeddings])
        self._documents.extend(documents)

    def query(self, query_embedding: Any, top_k: int = 5) -> list[SearchResult]:
        import numpy as np
        if self._embeddings is None or self.size == 0:
            return []
            
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        similarities = self._embeddings @ query_norm
        
        top_k = min(top_k, self.size)
        indices = np.argsort(similarities)[::-1][:top_k]
        
        return [
            SearchResult(
                index=int(idx),
                score=float(similarities[idx]),
                document=self._documents[idx],
            )
            for idx in indices
        ]


@dataclass(frozen=True)
class LocalRagPruneOutput:
    pruned_text: str
    annotations: list[dict[str, Any]]
    stats: dict[str, Any]
    warnings: list[str]


async def compute_local_rag_keep_set(
    *,
    lines: list[str],
    current_keep_set: set[int],
    goal_hint: str,
    keep_target: int,
    model_name: str = "all-MiniLM-L6-v2",
) -> set[int]:
    """Calcule le nouveau keep_set via similarité cosinus avec le goal_hint."""
    if not current_keep_set or keep_target <= 0:
        return set()
        
    active_indices = sorted(list(current_keep_set))
    if len(active_indices) <= keep_target:
        return current_keep_set.copy()
        
    active_lines = [lines[i] for i in active_indices]
    
    embedder = EmbeddingModel(model_name)
    line_embeddings = embedder.embed(active_lines)
    query_embedding = embedder.embed_single(goal_hint)
    
    store = VectorStore()
    store.add(line_embeddings, active_lines)
    
    results = store.query(query_embedding, top_k=keep_target)
    
    new_keep_set = {active_indices[r.index] for r in results}
    return new_keep_set


async def prune_text_with_local_rag(
    *,
    prune_id: str,
    text: str,
    goal_hint: str,
    source_type: Literal["code", "logs", "docs"],
    max_prune_ratio: float,
    min_keep_lines: int,
    annotate_lines: bool,
    include_markers: bool,
    model_name: str = "all-MiniLM-L6-v2",
) -> LocalRagPruneOutput:
    """Moteur principal du Local RAG pour l'élagage de texte."""
    started = time.perf_counter()
    lines = text.splitlines()
    n = len(lines)

    if n == 0:
        stats = {
            "backend": "local_rag",
            "original_lines": 0,
            "kept_lines": 0,
            "pruned_lines": 0,
            "pruned_ratio": 0.0,
            "tokens_est_before": 0,
            "tokens_est_after": 0,
            "elapsed_ms": 0,
            "used_fallback": False,
        }
        return LocalRagPruneOutput(pruned_text="", annotations=[], stats=stats, warnings=[])

    max_prune_ratio_n = max(0.0, min(1.0, float(max_prune_ratio)))
    min_keep_lines_n = max(0, int(min_keep_lines))

    from .deepinfra_engine import _compute_keep_target, _reconstruct_pruned_text
    keep_target = _compute_keep_target(n_lines=n, max_prune_ratio=max_prune_ratio_n, min_keep_lines=min_keep_lines_n)

    warnings: list[str] = []
    
    try:
        keep_set = await compute_local_rag_keep_set(
            lines=lines,
            current_keep_set=set(range(n)),
            goal_hint=goal_hint,
            keep_target=keep_target,
            model_name=model_name,
        )
    except ImportError as e:
        # Fallback to heuristic baseline if dependencies are not installed
        from .server import _baseline_prune
        pruned_text, annotations, stats = _baseline_prune(
            text=text,
            goal_hint=goal_hint,
            source_type=source_type,
            max_prune_ratio=max_prune_ratio,
            min_keep_lines=min_keep_lines,
            annotate_lines=annotate_lines,
            include_markers=include_markers,
        )
        stats["backend"] = "local_rag"
        stats["used_fallback"] = True
        stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        return LocalRagPruneOutput(
            pruned_text=pruned_text,
            annotations=annotations,
            stats=stats,
            warnings=["local_rag_fallback", str(e)]
        )
    except Exception as e:
        # Unexpected error fallback
        from .server import _baseline_prune
        pruned_text, annotations, stats = _baseline_prune(
            text=text,
            goal_hint=goal_hint,
            source_type=source_type,
            max_prune_ratio=max_prune_ratio,
            min_keep_lines=min_keep_lines,
            annotate_lines=annotate_lines,
            include_markers=include_markers,
        )
        stats["backend"] = "local_rag"
        stats["used_fallback"] = True
        stats["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
        return LocalRagPruneOutput(
            pruned_text=pruned_text,
            annotations=annotations,
            stats=stats,
            warnings=["local_rag_error", str(e)]
        )

    # Reconstruct text with annotations
    pruned_text, annotations = _reconstruct_pruned_text(
        prune_id=prune_id,
        lines=lines,
        keep_set=keep_set,
        goal_hint=goal_hint,
        annotate_lines=annotate_lines,
        include_markers=include_markers,
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    kept_lines = len(keep_set)
    pruned_lines = n - kept_lines
    pruned_ratio = pruned_lines / n if n > 0 else 0.0

    stats = {
        "backend": "local_rag",
        "original_lines": n,
        "kept_lines": kept_lines,
        "pruned_lines": pruned_lines,
        "pruned_ratio": round(pruned_ratio, 6),
        "tokens_est_before": count_tokens_text(text),
        "tokens_est_after": count_tokens_text(pruned_text),
        "elapsed_ms": elapsed_ms,
        "used_fallback": False,
    }

    return LocalRagPruneOutput(pruned_text=pruned_text, annotations=annotations, stats=stats, warnings=warnings)
