"""Observation masking (Schéma 1).

But: réduire les tokens/coûts en masquant les anciens tool results (role=tool)
dans l'historique `messages` avant envoi au provider.

Voir: `.shrimp_task_manager/plan/observation-masking-schema1-tech-spec.md`.
"""

from .schema1 import MaskPolicy, mask_old_tool_results

__all__ = [
    "MaskPolicy",
    "mask_old_tool_results",
]
