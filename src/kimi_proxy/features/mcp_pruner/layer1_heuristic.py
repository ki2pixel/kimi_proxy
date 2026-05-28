"""kimi_proxy.features.mcp_pruner.layer1_heuristic

Pruner déterministe (Layer 1).
- Nettoyage des chaînes Base64/Hash longues.
- Réduction heuristique des lignes en respectant le ratio.
"""

from __future__ import annotations

import re

# Nettoyage des data URIs (ex: data:image/png;base64,iVBO...)
_B64_DATA_URI_RE = re.compile(r"data:[a-zA-Z0-9/+-]+;base64,[a-zA-Z0-9+/=]+")
# Nettoyage des longues chaînes continues (souvent des dumps hexa/base64 ou JWT géants)
_LONG_HASH_RE = re.compile(r"(?<![a-zA-Z0-9+/=])[a-zA-Z0-9+/=]{200,}(?![a-zA-Z0-9+/=])")


def clean_base64_and_hashes_inline(lines: list[str]) -> None:
    """Modifie la liste en place pour remplacer les gros blocs de données par des placeholders."""
    for i, line in enumerate(lines):
        if len(line) > 200:
            # Remplacement des data URIs
            new_line = _B64_DATA_URI_RE.sub("<stripped_base64_uri>", line)
            # Remplacement des longs hashes/blobs continus
            new_line = _LONG_HASH_RE.sub("<stripped_long_hash>", new_line)
            if new_line != line:
                lines[i] = new_line


def compute_heuristic_keep_set(
    *,
    lines: list[str],
    current_keep_set: set[int],
    keep_target: int,
) -> set[int]:
    """
    Réduit le `current_keep_set` pour atteindre `keep_target` en utilisant
    une distribution uniforme (saute des lignes de façon régulière).
    """
    active_indices = sorted(list(current_keep_set))
    n_active = len(active_indices)
    
    if n_active <= keep_target:
        return current_keep_set.copy()
        
    if keep_target <= 0:
        return set()

    step = n_active / keep_target
    new_keep = set()
    
    for i in range(keep_target):
        # On sélectionne uniformément dans les index actifs
        idx = int(i * step)
        if idx < n_active:
            new_keep.add(active_indices[idx])
            
    # S'assurer qu'on garde la première et la dernière ligne si possible
    if active_indices[0] not in new_keep and len(new_keep) < keep_target:
        new_keep.add(active_indices[0])
    if active_indices[-1] not in new_keep and len(new_keep) < keep_target:
        new_keep.add(active_indices[-1])
        
    return new_keep
