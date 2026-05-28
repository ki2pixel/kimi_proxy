"""
MCE — Squeeze Engine Layer 2: Semantic Router (CPU-Friendly RAG)
Chunks pruned payload, embeds chunks + agent query, extracts only
the most relevant content via cosine-similarity search.
"""

from __future__ import annotations

import json
from typing import Any

from models.embeddings import EmbeddingModel
from models.vector_store import VectorStore
from utils.chunker import chunk_text
from utils.logger import get_logger

_log = get_logger("SemanticRouter")


class Layer2SemanticRouter:
    """
    CPU-bound semantic relevance filter.

    Given a pruned payload that is still too large, this layer:
    1. Chunks the payload into reasonably-sized pieces.
    2. Embeds all chunks using the micro-embedding model.
    3. Embeds the agent's original query.
    4. Extracts only the top-k most relevant chunks.
    """

    def __init__(
        self,
        top_k: int = 5,
        max_chunk_tokens: int = 500,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self._top_k = top_k
        self._max_chunk_tokens = max_chunk_tokens
        self._embedder = EmbeddingModel(model_name)

    def route(self, payload: Any, agent_query: str) -> Any:
        """
        Semantically filter *payload* against the agent's *query*.

        Args:
            payload: The pruned tool response (str, dict, or list).
            agent_query: The original question/intent from the agent.

        Returns:
            The filtered payload, preserving the original type when possible.
            If the original was structured (dict/list) and can't be re-parsed,
            returns {"_mce_summary": "..."} to maintain type safety.
        """
        original_type = type(payload)
        text = self._to_text(payload)

        # Chunk the payload
        chunks = chunk_text(text, max_tokens=self._max_chunk_tokens)
        if not chunks:
            return payload

        _log.info(
            f"Chunked payload into {len(chunks)} pieces, "
            f"selecting top-{self._top_k}"
        )

        # Embed chunks + query
        chunk_embeddings = self._embedder.embed(chunks)
        query_embedding = self._embedder.embed_single(agent_query)

        # Build temporary in-memory vector store
        store = VectorStore()
        store.add(chunk_embeddings, chunks)

        # Retrieve most relevant chunks
        results = store.query(query_embedding, top_k=self._top_k)

        if not results:
            return payload

        # Reconstruct output preserving original order
        relevant_indices = sorted(r.index for r in results)
        relevant_chunks = [chunks[i] for i in relevant_indices]

        _log.info(
            f"[mce.success]Extracted {len(relevant_chunks)}/{len(chunks)} chunks[/mce.success] "
            f"(scores: {', '.join(f'{r.score:.3f}' for r in results)})"
        )

        summary = "\n\n".join(relevant_chunks)

        # Attempt to preserve original payload type
        if original_type is str:
            return summary
        try:
            parsed = json.loads(summary)
            if isinstance(parsed, original_type):
                return parsed
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Fallback: wrap in a dict so structured callers still get a dict
        return {"_mce_summary": summary, "_mce_original_type": original_type.__name__}

    @staticmethod
    def _to_text(payload: Any) -> str:
        """Convert any payload to a searchable text string."""
        if isinstance(payload, str):
            return payload
        try:
            return json.dumps(payload, default=str, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(payload)
