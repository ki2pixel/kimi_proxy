"""Observation masking (Schéma 1).

But: réduire les tokens/coûts en masquant les anciens tool results (role=tool)
dans l'historique `messages` avant envoi au provider.

Voir: `.shrimp_task_manager/plan/observation-masking-schema1-tech-spec.md`.
"""

from .schema1 import MaskPolicy, mask_old_tool_results


def build_mask_policy_from_config(schema1_cfg: object) -> MaskPolicy:
    """Construit un MaskPolicy à partir de la config TOML chargée.

    Centralise la conversion ObservationMaskingSchema1Config → MaskPolicy
    pour éviter la duplication entre proxy.py et passthrough.py.
    """
    return MaskPolicy(
        enabled=getattr(schema1_cfg, "enabled", False),
        window_turns=getattr(schema1_cfg, "window_turns", 8),
        keep_errors=getattr(schema1_cfg, "keep_errors", True),
        keep_last_k_per_tool=getattr(schema1_cfg, "keep_last_k_per_tool", None),
        placeholder_template=getattr(
            schema1_cfg,
            "placeholder_template",
            MaskPolicy.placeholder_template,
        ),
    )


__all__ = [
    "MaskPolicy",
    "mask_old_tool_results",
    "build_mask_policy_from_config",
]
