"""
Compaction Phase 2 - Fonctionnalités Utilisateur pour Context Compaction.

Ce module fournit le service SimpleCompaction pour la gestion automatique
de la compaction du contexte LLM avec:
- Compaction manuelle avec preview
- Triggers automatiques avec seuils configurables
- Toggle auto-compaction par session
- Visualisation avancée et graphiques
"""

from .simple_compaction import (
    SimpleCompaction,
    CompactionResult,
    CompactionConfig,
    get_compactor,
    create_compactor,
)

from .storage import (
    persist_compaction_result,
    get_session_compaction_stats,
    get_all_compaction_stats,
    set_session_reserved_tokens,
    get_compaction_timeline,
)

from .auto_trigger import (
    CompactionAutoTrigger,
    AutoTriggerConfig,
    get_auto_trigger,
)

__all__ = [
    # SimpleCompaction
    "SimpleCompaction",
    "CompactionResult",
    "CompactionConfig",
    "get_compactor",
    "create_compactor",
    # Storage
    "persist_compaction_result",
    "get_session_compaction_stats",
    "get_all_compaction_stats",
    "set_session_reserved_tokens",
    "get_compaction_timeline",
    # Auto Trigger (Phase 2)
    "CompactionAutoTrigger",
    "AutoTriggerConfig",
    "get_auto_trigger",
]
