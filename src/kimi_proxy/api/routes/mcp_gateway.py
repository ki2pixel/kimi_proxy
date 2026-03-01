"""Routes API — MCP Gateway.

Expose un endpoint HTTP qui forwarde des requêtes JSON-RPC 2.0 vers des serveurs MCP
locaux, puis applique une troncature (Observation Masking) sur les réponses volumineuses.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...config.loader import get_config, get_mcp_tool_pruning_config
from ...features.mcp.gateway import MCPGatewayService
from ...features.mcp_tool_pruning import (
    MCPToolPruningMetricsCollector,
    maybe_prune_jsonrpc_response,
    resolve_mcp_tool_pruning_config,
)
from ...features.mcp_tool_pruning.pruner_client import (
    build_prune_text_request_jsonrpc,
    extract_prune_result_from_jsonrpc_response,
)
from ...features.mcp_pruner.spec import PruneOptionsDict, SourceType
from ...proxy.mcp_gateway_rpc import MCPGatewayUpstreamError, forward_jsonrpc


router = APIRouter()


# Observabilité (Phase 2D): métriques metadata-only, in-memory.
# Exposition optionnelle via /health (voir routes/health.py).
_MCP_TOOL_PRUNING_METRICS = MCPToolPruningMetricsCollector()


def get_mcp_tool_pruning_metrics_collector() -> MCPToolPruningMetricsCollector:
    return _MCP_TOOL_PRUNING_METRICS


def _as_dict(obj: object) -> dict[str, object] | None:
    if isinstance(obj, dict):
        # Cast défensif: clé str attendue pour JSON-RPC.
        result: dict[str, object] = {}
        for k, v in obj.items():
            if not isinstance(k, str):
                return None
            result[k] = v
        return result
    return None


@router.post("/mcp-gateway/{server_name}/rpc")
async def api_mcp_gateway_rpc(server_name: str, request: Request):
    """Forwarde un JSON-RPC 2.0 brut vers un serveur MCP local puis masque la réponse."""

    service = MCPGatewayService()

    request_json_obj = await request.json()
    request_json = _as_dict(request_json_obj)
    if request_json is None:
        error_payload = service.build_jsonrpc_error(
            request_json_obj,
            code=-32600,
            message="Requête JSON-RPC invalide (attendu objet JSON)",
        )
        return JSONResponse(content=error_payload, status_code=400)

    try:
        upstream_response = await forward_jsonrpc(server_name, request_json)

        # Phase 2 (wrapper hybride): pruning conditionnel avant masking.
        # Fail-open: toute erreur => upstream_response intact.
        try:
            toml_cfg = get_mcp_tool_pruning_config(get_config())
            pruning_cfg = resolve_mcp_tool_pruning_config(toml_cfg)

            async def _pruner_callable(
                *,
                request_id: int,
                text: str,
                goal_hint: str,
                source_type: SourceType,
                options: PruneOptionsDict,
                call_timeout_ms: int,
            ):
                # NOTE: I/O HTTP conservée côté Proxy via forward_jsonrpc.
                req = build_prune_text_request_jsonrpc(
                    request_id=request_id,
                    text=text,
                    goal_hint=goal_hint,
                    source_type=source_type,
                    options=options,
                )
                timeout_s = max(0.001, float(call_timeout_ms) / 1000.0)
                try:
                    resp = await forward_jsonrpc("pruner", req, timeout_s=timeout_s)
                except MCPGatewayUpstreamError:
                    return None
                except Exception:
                    return None
                return extract_prune_result_from_jsonrpc_response(resp)

            pruned_response = await maybe_prune_jsonrpc_response(
                server_name=server_name,
                request_json=request_json,
                response_json=upstream_response,
                cfg=pruning_cfg,
                pruner=_pruner_callable,
                metrics=_MCP_TOOL_PRUNING_METRICS,
            )
        except Exception:
            pruned_response = upstream_response

        masked = service.mask_jsonrpc_response(pruned_response)
        return JSONResponse(content=masked)
    except MCPGatewayUpstreamError as e:
        # Map vers codes JSON-RPC spécifiques au gateway
        if e.code == "unknown_server":
            code = -32001
            status = 404
        elif e.code in {"timeout", "connect_error"}:
            code = -32002
            status = 502
        elif e.code == "invalid_json":
            code = -32003
            status = 502
        else:
            code = -32603
            status = 502

        error_payload = service.build_jsonrpc_error(
            request_json,
            code=code,
            message=e.message,
            data=e.details,
        )
        return JSONResponse(content=error_payload, status_code=status)
