"""kimi_proxy.features.mcp_tool_pruning.pruner_client

Helpers (sans I/O) pour appeler le serveur MCP Pruner via JSON-RPC 2.0.

Ce module n'effectue pas d'appels réseau: il construit et parse les payloads.
"""

from __future__ import annotations

import json
from typing import TypedDict

from ..mcp_pruner.spec import PruneOptionsDict, SourceType


class PruneTextResult(TypedDict, total=False):
    prune_id: str
    pruned_text: str
    warnings: list[str]
    stats: dict[str, object]


class JsonRpcRequest(TypedDict):
    jsonrpc: str
    id: int
    method: str
    params: dict[str, object]


def build_prune_text_request_jsonrpc(
    *,
    request_id: int,
    text: str,
    goal_hint: str,
    source_type: SourceType,
    options: PruneOptionsDict,
) -> JsonRpcRequest:
    return {
        "jsonrpc": "2.0",
        "id": int(request_id),
        "method": "tools/call",
        "params": {
            "name": "prune_text",
            "arguments": {
                "text": text,
                "goal_hint": goal_hint,
                "source_type": source_type,
                "options": dict(options),
            },
        },
    }


def extract_prune_result_from_jsonrpc_response(response_json: object) -> PruneTextResult | None:
    """Parse la réponse JSON-RPC du serveur pruner.

    Le serveur pruner renvoie généralement un tool-result MCP:
      response.result.content[0].text = JSON sérialisé (PruneResult).
    """

    if not isinstance(response_json, dict) or response_json.get("jsonrpc") != "2.0":
        return None
    if "error" in response_json:
        return None

    result_obj = response_json.get("result")
    if not isinstance(result_obj, dict):
        return None

    content_obj = result_obj.get("content")
    if not isinstance(content_obj, list) or not content_obj:
        return None

    first = content_obj[0]
    if not isinstance(first, dict):
        return None

    text_obj = first.get("text")
    if not isinstance(text_obj, str) or not text_obj:
        return None

    try:
        parsed = json.loads(text_obj)
    except Exception:
        return None

    if not isinstance(parsed, dict):
        return None

    prune_id_obj = parsed.get("prune_id")
    pruned_text_obj = parsed.get("pruned_text")
    if not isinstance(prune_id_obj, str) or not isinstance(pruned_text_obj, str):
        return None

    out: PruneTextResult = {
        "prune_id": prune_id_obj,
        "pruned_text": pruned_text_obj,
    }

    warnings_obj = parsed.get("warnings")
    if isinstance(warnings_obj, list):
        warnings: list[str] = []
        for it in warnings_obj:
            if isinstance(it, str):
                warnings.append(it)
        out["warnings"] = warnings

    stats_obj = parsed.get("stats")
    if isinstance(stats_obj, dict):
        # Metadata-only / best-effort.
        out["stats"] = {str(k): v for k, v in stats_obj.items() if isinstance(k, str)}

    return out
