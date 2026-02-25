"""Routes API — MCP Gateway.

Expose un endpoint HTTP qui forwarde des requêtes JSON-RPC 2.0 vers des serveurs MCP
locaux, puis applique une troncature (Observation Masking) sur les réponses volumineuses.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...features.mcp.gateway import MCPGatewayService
from ...proxy.mcp_gateway_rpc import MCPGatewayUpstreamError, forward_jsonrpc


router = APIRouter()


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
        masked = service.mask_jsonrpc_response(upstream_response)
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
