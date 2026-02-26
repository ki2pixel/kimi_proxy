"""kimi_proxy.proxy.context_pruning

Intégration Proxy (Lot C2): appel au serveur MCP Pruner (HTTP JSON-RPC /rpc)
pour élaguer du contenu textuel *sans casser* les invariants tool-calling.

Design:
- Transformation conservatrice: on ne modifie que `message["content"]` (str)
  de certains messages; on ne touche pas à la longueur/ordre des messages.
- Local-first: appel uniquement à un serveur MCP local via `forward_jsonrpc`.
- Fail-open: toute erreur => no-op (contenu inchangé) + un résumé metadata-only.

Notes:
- Ce module est dans la couche Proxy (I/O HTTP autorisé).
- Le parsing du résultat est best-effort (robustesse et compat rétro).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from ..config.loader import ContextPruningConfig
from .mcp_gateway_rpc import forward_jsonrpc, MCPGatewayUpstreamError


ChatMessage = dict[str, object]
SourceType = Literal["code", "logs", "docs"]


@dataclass(frozen=True)
class PrunerStats:
    tokens_est_before: int | None
    tokens_est_after: int | None
    used_fallback: bool | None
    pruned_ratio: float | None


@dataclass(frozen=True)
class PrunerOutcome:
    prune_id: str
    pruned_text: str
    warnings: list[str]
    stats: PrunerStats
    annotation_count: int


@dataclass(frozen=True)
class ContextPruningSummary:
    enabled: bool
    calls_attempted: int
    messages_pruned: int
    used_fallback_count: int
    warnings: list[str]


def _safe_get_dict(obj: object, key: str) -> dict[str, object] | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, dict):
        return value
    return None


def _safe_get_list(obj: object, key: str) -> list[object] | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, list):
        return value
    return None


def _safe_get_str(obj: object, key: str) -> str | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, str):
        return value
    return None


def _safe_get_bool(obj: object, key: str) -> bool | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, bool):
        return value
    return None


def _safe_get_int(obj: object, key: str) -> int | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _safe_get_float(obj: object, key: str) -> float | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _safe_get_str_list(obj: object, key: str) -> list[str] | None:
    items = _safe_get_list(obj, key)
    if items is None:
        return None
    out: list[str] = []
    for it in items:
        if isinstance(it, str):
            out.append(it)
    return out


def _parse_pruner_tool_payload(raw: object) -> PrunerOutcome | None:
    """Parse le JSON sérialisé dans `result.content[0].text`.

    Retourne None si structure inattendue.
    """

    if not isinstance(raw, dict):
        return None

    prune_id = _safe_get_str(raw, "prune_id")
    pruned_text = _safe_get_str(raw, "pruned_text")
    if prune_id is None or pruned_text is None:
        return None

    warnings = _safe_get_str_list(raw, "warnings") or []

    stats_obj = _safe_get_dict(raw, "stats") or {}
    stats = PrunerStats(
        tokens_est_before=_safe_get_int(stats_obj, "tokens_est_before"),
        tokens_est_after=_safe_get_int(stats_obj, "tokens_est_after"),
        used_fallback=_safe_get_bool(stats_obj, "used_fallback"),
        pruned_ratio=_safe_get_float(stats_obj, "pruned_ratio"),
    )

    annotations = _safe_get_list(raw, "annotations") or []
    annotation_count = len(annotations)

    return PrunerOutcome(
        prune_id=prune_id,
        pruned_text=pruned_text,
        warnings=warnings,
        stats=stats,
        annotation_count=annotation_count,
    )


def _extract_tool_payload_from_jsonrpc_response(response: object) -> dict[str, object] | None:
    if not isinstance(response, dict):
        return None

    if "error" in response:
        return None

    result_obj = response.get("result")
    if not isinstance(result_obj, dict):
        return None

    content_obj = result_obj.get("content")
    if not isinstance(content_obj, list) or not content_obj:
        return None

    first = content_obj[0]
    if not isinstance(first, dict):
        return None

    text = first.get("text")
    if not isinstance(text, str) or not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    return parsed if isinstance(parsed, dict) else None


async def prune_text_via_pruner_mcp(
    *,
    text: str,
    goal_hint: str,
    source_type: SourceType,
    cfg: ContextPruningConfig,
    request_id: int,
) -> PrunerOutcome | None:
    """Appelle le tool `prune_text` via MCP pruner; retourne un outcome best-effort."""

    request_json: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "prune_text",
            "arguments": {
                "text": text,
                "goal_hint": goal_hint,
                "source_type": source_type,
                "options": {
                    "max_prune_ratio": cfg.max_prune_ratio,
                    "min_keep_lines": cfg.min_keep_lines,
                    "timeout_ms": cfg.timeout_ms,
                    "annotate_lines": cfg.annotate_lines,
                    "include_markers": cfg.include_markers,
                },
            },
        },
    }

    timeout_s = max(0.001, cfg.call_timeout_ms / 1000.0)

    try:
        response = await forward_jsonrpc("pruner", request_json, timeout_s=timeout_s)
    except MCPGatewayUpstreamError:
        return None
    except Exception:
        return None

    payload = _extract_tool_payload_from_jsonrpc_response(response)
    if payload is None:
        return None

    return _parse_pruner_tool_payload(payload)


async def prune_tool_messages_best_effort(
    *,
    messages: list[ChatMessage],
    goal_hint: str,
    cfg: ContextPruningConfig,
    source_type: SourceType = "logs",
) -> tuple[list[ChatMessage], ContextPruningSummary]:
    """Prune uniquement les messages `role="tool"`.

    Rationale:
    - Préserve les invariants tool-calling.
    - S'aligne avec le Schéma 1 (masking) qui opère aussi sur `role="tool"`.
    """

    if not cfg.enabled:
        return messages, ContextPruningSummary(
            enabled=False,
            calls_attempted=0,
            messages_pruned=0,
            used_fallback_count=0,
            warnings=[],
        )

    output: list[ChatMessage] = []
    calls_attempted = 0
    messages_pruned = 0
    used_fallback_count = 0
    warnings: list[str] = []

    req_id = 100
    for msg in messages:
        role = msg.get("role")
        if role != "tool":
            output.append(dict(msg))
            continue

        content_obj = msg.get("content")
        if not isinstance(content_obj, str):
            output.append(dict(msg))
            continue

        if len(content_obj) < cfg.min_chars_to_prune:
            output.append(dict(msg))
            continue

        calls_attempted += 1
        req_id += 1

        outcome = await prune_text_via_pruner_mcp(
            text=content_obj,
            goal_hint=goal_hint,
            source_type=source_type,
            cfg=cfg,
            request_id=req_id,
        )

        if outcome is None:
            output.append(dict(msg))
            continue

        if outcome.stats.used_fallback is True:
            used_fallback_count += 1
        for w in outcome.warnings:
            if w not in warnings:
                warnings.append(w)

        pruned_msg = dict(msg)
        pruned_msg["content"] = outcome.pruned_text
        pruned_msg["_pruner"] = {
            "prune_id": outcome.prune_id,
            "annotation_count": outcome.annotation_count,
            "warnings": outcome.warnings,
            "used_fallback": outcome.stats.used_fallback,
        }
        output.append(pruned_msg)
        messages_pruned += 1

    return output, ContextPruningSummary(
        enabled=True,
        calls_attempted=calls_attempted,
        messages_pruned=messages_pruned,
        used_fallback_count=used_fallback_count,
        warnings=warnings,
    )
