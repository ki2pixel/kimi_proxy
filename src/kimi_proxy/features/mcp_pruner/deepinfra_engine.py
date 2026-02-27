"""kimi_proxy.features.mcp_pruner.deepinfra_engine

Moteur de pruning basé sur DeepInfra (Phase 1 POC).

Responsabilité:
- Transformer un texte en lignes.
- Faire un reranking DeepInfra (goal_hint = query, lignes = documents).
- Sélectionner un sous-ensemble de lignes à conserver (top-K) en respectant
  strictement `max_prune_ratio` et `min_keep_lines`.
- Reconstruire `pruned_text` + `annotations` + markers canonique.

Important:
- Les markers ne doivent **jamais** être préfixés par "N│".
- Ce module ne gère pas le fail-open global: en cas d'exception DeepInfra, la
  stratégie de fallback sera orchestrée par le backend manager (Task 3).
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from typing import Literal

from kimi_proxy.core.tokens import count_tokens_text

from .deepinfra_client import DeepInfraClient


JsonDict = dict[str, object]
SourceType = Literal["code", "logs", "docs"]


@dataclass(frozen=True)
class DeepInfraPruneOutput:
    pruned_text: str
    annotations: list[JsonDict]
    stats: JsonDict
    warnings: list[str]


async def prune_text_with_deepinfra(
    *,
    prune_id: str,
    text: str,
    goal_hint: str,
    source_type: SourceType,
    max_prune_ratio: float,
    min_keep_lines: int,
    annotate_lines: bool,
    include_markers: bool,
    max_docs: int,
    deepinfra_client: DeepInfraClient,
) -> DeepInfraPruneOutput:
    started = time.perf_counter()
    lines = text.splitlines()
    n = len(lines)

    if n == 0:
        stats: JsonDict = {
            "backend": "deepinfra",
            "original_lines": 0,
            "kept_lines": 0,
            "pruned_lines": 0,
            "pruned_ratio": 0.0,
            "tokens_est_before": 0,
            "tokens_est_after": 0,
            "elapsed_ms": 0,
            "used_fallback": False,
            "deepinfra_latency_ms": 0,
            "deepinfra_docs_scored": 0,
            "deepinfra_docs_total": 0,
            "deepinfra_http_status": 200,
        }
        return DeepInfraPruneOutput(pruned_text="", annotations=[], stats=stats, warnings=[])

    max_prune_ratio_n = max(0.0, min(1.0, float(max_prune_ratio)))
    min_keep_lines_n = max(0, int(min_keep_lines))

    keep_target = _compute_keep_target(n_lines=n, max_prune_ratio=max_prune_ratio_n, min_keep_lines=min_keep_lines_n)

    max_docs_n = max(1, int(max_docs))
    doc_indices = _select_doc_indices(n_lines=n, max_docs=max_docs_n)
    warnings: list[str] = []
    if len(doc_indices) < n:
        warnings.append("deepinfra_docs_truncated")

    docs = [lines[i] for i in doc_indices]
    rerank_result = await deepinfra_client.rerank(query=goal_hint, documents=docs)

    # Remap doc scores -> line scores (missing docs default 0.0)
    line_scores: dict[int, float] = {}
    for doc_i, line_i in enumerate(doc_indices):
        score = float(rerank_result.scores_by_index.get(doc_i, 0.0))
        line_scores[line_i] = score

    # Score manquant = 0.0 (stratégie déterministe)
    scored_indices = list(range(n))
    scored_indices.sort(key=lambda i: (-float(line_scores.get(i, 0.0)), i))
    keep_set = set(scored_indices[:keep_target])

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
        "backend": "deepinfra",
        "original_lines": n,
        "kept_lines": kept_lines,
        "pruned_lines": pruned_lines,
        "pruned_ratio": round(pruned_ratio, 6),
        "tokens_est_before": count_tokens_text(text),
        "tokens_est_after": count_tokens_text(pruned_text),
        "elapsed_ms": elapsed_ms,
        "used_fallback": False,
        "deepinfra_latency_ms": int(rerank_result.elapsed_ms),
        "deepinfra_docs_scored": len(doc_indices),
        "deepinfra_docs_total": n,
        "deepinfra_http_status": 200,
    }

    return DeepInfraPruneOutput(pruned_text=pruned_text, annotations=annotations, stats=stats, warnings=warnings)


def _compute_keep_target(*, n_lines: int, max_prune_ratio: float, min_keep_lines: int) -> int:
    n = max(0, int(n_lines))
    if n == 0:
        return 0

    max_prune_ratio_n = max(0.0, min(1.0, float(max_prune_ratio)))
    min_keep_lines_n = max(0, int(min_keep_lines))

    # k = max(min_keep_lines, ceil(n*(1-max_prune_ratio)))
    keep_by_ratio = int(math.ceil(n * (1.0 - max_prune_ratio_n)))
    k = max(min_keep_lines_n, keep_by_ratio)
    return min(n, max(0, k))


def _select_doc_indices(*, n_lines: int, max_docs: int) -> list[int]:
    """Sélectionne les lignes à scorer (clamp à max_docs).

    Stratégie: échantillonnage uniforme et déterministe sur [0..n-1].
    """

    n = max(0, int(n_lines))
    if n == 0:
        return []

    m = max(1, int(max_docs))
    if m >= n:
        return list(range(n))
    if m == 1:
        return [0]

    indices: list[int] = []
    for j in range(m):
        # round() pour couvrir les extrémités; clamp sécurité
        idx = int(round(j * (n - 1) / (m - 1)))
        idx = max(0, min(n - 1, idx))
        if idx not in indices:
            indices.append(idx)

    # Si round() a créé des doublons (rare), compléter avec les indices manquants
    cursor = 0
    while len(indices) < m and cursor < n:
        if cursor not in indices:
            indices.append(cursor)
        cursor += 1

    indices.sort()
    return indices[:m]


def _reconstruct_pruned_text(
    *,
    prune_id: str,
    lines: list[str],
    keep_set: set[int],
    goal_hint: str,
    annotate_lines: bool,
    include_markers: bool,
) -> tuple[str, list[JsonDict]]:
    n = len(lines)
    kept_sorted = sorted(keep_set)

    reason = _prune_reason(goal_hint)

    out_lines: list[str] = []
    annotations: list[JsonDict] = []

    def emit_kept(i: int) -> None:
        content = lines[i]
        if annotate_lines:
            out_lines.append(f"{i + 1}│ {content}")
        else:
            out_lines.append(content)

    def emit_pruned_block(start_idx: int, end_idx: int) -> None:
        if start_idx > end_idx:
            return
        pruned_count = end_idx - start_idx + 1
        marker = _marker_text(
            prune_id=prune_id,
            start_line=start_idx + 1,
            end_line=end_idx + 1,
            count=pruned_count,
            reason=reason,
        )
        annotations.append(
            {
                "kind": "pruned_block",
                "original_start_line": start_idx + 1,
                "original_end_line": end_idx + 1,
                "pruned_line_count": pruned_count,
                "reason": reason,
                "marker": marker,
            }
        )
        if include_markers:
            # IMPORTANT: le marker ne doit pas être préfixé par "N│".
            out_lines.append(marker)

    if not kept_sorted:
        emit_pruned_block(0, n - 1)
        return "\n".join(out_lines), annotations

    last_kept = -1
    for k in kept_sorted:
        if k > last_kept + 1:
            emit_pruned_block(last_kept + 1, k - 1)
        emit_kept(k)
        last_kept = k
    if last_kept < n - 1:
        emit_pruned_block(last_kept + 1, n - 1)

    return "\n".join(out_lines), annotations


def _marker_text(*, prune_id: str, start_line: int, end_line: int, count: int, reason: str) -> str:
    # Une seule ligne, format canonique.
    return f"⟦PRUNÉ: prune_id={prune_id} lignes {start_line}-{end_line} ({count}) raison={reason}⟧"


def _prune_reason(goal_hint: str) -> str:
    keyword = _first_keyword(goal_hint)
    if keyword is None:
        return "hors focus"
    return f"hors focus: {keyword}"


def _first_keyword(text: str) -> str | None:
    # 4+ chars: évite des tokens trop courts, et reste déterministe.
    tokens = re.findall(r"[A-Za-z0-9_]{4,}", text.lower())
    seen: set[str] = set()
    for t in tokens:
        if t not in seen:
            seen.add(t)
            return t
    return None
