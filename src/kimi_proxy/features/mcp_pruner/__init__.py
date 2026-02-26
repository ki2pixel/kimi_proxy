"""MCP Pruner (SWE‑Pruner) — package de spécification.

Ce package est volontairement minimal à ce stade (Lot A1):
- uniquement des types de contrat (TypedDict / dataclasses)
- aucune logique d’exécution

L’implémentation du serveur HTTP MCP Pruner est prévue dans le Lot A2.
"""

from .spec import (
    PruneOptions,
    PruneOptionsDict,
    PruneRequest,
    PrunedBlockAnnotation,
    PruneResult,
    PruneStats,
    RecoverMetadata,
    RecoverRange,
    RecoverRequest,
    RecoverResult,
    SourceType,
)

__all__ = [
    "PruneOptions",
    "PruneOptionsDict",
    "PruneRequest",
    "PrunedBlockAnnotation",
    "PruneResult",
    "PruneStats",
    "RecoverMetadata",
    "RecoverRange",
    "RecoverRequest",
    "RecoverResult",
    "SourceType",
]
