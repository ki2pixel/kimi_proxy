"""kimi_proxy.features.mcp_pruner.spec

Contrat (types de référence) pour le serveur MCP Pruner.

Important:
- Ce module est une **spécification**; il n’implémente aucun pruning.
- Objectif: fournir des schémas stables (TypedDict + dataclasses) pour l’intégration
  future côté Kimi Proxy (appel MCP HTTP local + fallback no-op).

Référence doc: `docs/features/mcp-pruner.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


SourceType = Literal["code", "logs", "docs"]


@dataclass(frozen=True)
class PruneOptions:
    """Options de pruning.

    Ces options sont conçues pour être sérialisées en JSON et envoyées au serveur MCP.
    """

    max_prune_ratio: float
    min_keep_lines: int
    timeout_ms: int
    annotate_lines: bool
    include_markers: bool


class PruneOptionsDict(TypedDict):
    max_prune_ratio: float
    min_keep_lines: int
    timeout_ms: int
    annotate_lines: bool
    include_markers: bool


class PruneRequest(TypedDict):
    text: str
    goal_hint: str
    source_type: SourceType
    options: PruneOptionsDict


class PrunedBlockAnnotation(TypedDict):
    kind: Literal["pruned_block"]
    original_start_line: int
    original_end_line: int
    pruned_line_count: int
    reason: str
    marker: str


class PruneStats(TypedDict):
    original_lines: int
    kept_lines: int
    pruned_lines: int
    pruned_ratio: float
    tokens_est_before: int
    tokens_est_after: int
    elapsed_ms: int
    used_fallback: bool


class PruneResult(TypedDict):
    prune_id: str
    pruned_text: str
    annotations: list[PrunedBlockAnnotation]
    stats: PruneStats
    warnings: list[str]


class RecoverRange(TypedDict):
    start_line: int
    end_line: int


class RecoverRequest(TypedDict):
    prune_id: str
    ranges: list[RecoverRange]
    include_line_numbers: bool


class RecoverMetadata(TypedDict):
    prune_id: str
    ranges: list[RecoverRange]
    line_numbering: Literal["original"]


class RecoverResult(TypedDict):
    raw_text: str
    metadata: RecoverMetadata
