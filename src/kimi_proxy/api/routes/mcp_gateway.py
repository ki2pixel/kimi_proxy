"""Routes API — MCP Gateway.

Expose un endpoint HTTP qui forwarde des requêtes JSON-RPC 2.0 vers des serveurs MCP
locaux, puis applique une troncature (Observation Masking) sur les réponses volumineuses.

Ce module consolide la logique de forwarding JSON-RPC (anciennement dans
proxy/mcp_gateway_rpc.py) pour réduire l'indirection.
"""

from __future__ import annotations

from dataclasses import dataclass
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import hashlib
import json
import time

import httpx

from ...config.loader import get_config, get_mcp_tool_pruning_config, get_mcp_gateway_config, MCPGatewayConfig
from ...features.mcp.gateway import MCPGatewayService
from ...features.mcp.detector import MCPCircuitBreaker
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


# ============================================================================
# Forwarding JSON-RPC (ex-proxy/mcp_gateway_rpc.py)
# ============================================================================

@dataclass(frozen=True)
class MCPGatewayUpstreamError(Exception):
    """Erreur lors de l'appel upstream vers un serveur MCP local."""

    code: str
    message: str
    details: dict[str, object] | None = None

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} - {self.details}"
        return f"[{self.code}] {self.message}"


def get_mcp_server_base_url(server_name: str) -> str | None:
    """Retourne l'URL de base d'un serveur MCP local supporté.

    Mapping basé sur `scripts/start-mcp-servers.sh`.
    """

    mapping: dict[str, str] = {
        "context-compression": "http://127.0.0.1:8001",
        "sequential-thinking": "http://127.0.0.1:8003",
        "fast-filesystem": "http://127.0.0.1:8004",
        "json-query": "http://127.0.0.1:8005",
        "pruner": "http://127.0.0.1:8006",
    }
    return mapping.get(server_name)


async def forward_jsonrpc(
    server_name: str,
    request_json: object,
    *,
    timeout_s: float = 30.0,
) -> object:
    """Forwarde une requête JSON-RPC brute vers `{base_url}/rpc`.

    Args:
        server_name: nom logique du serveur MCP local
        request_json: payload JSON-RPC 2.0 (dict JSON)
        timeout_s: timeout global en secondes

    Returns:
        La réponse JSON (objet Python) retournée par le serveur MCP.

    Raises:
        MCPGatewayUpstreamError: pour erreurs de réseau/protocole.
    """

    base_url = get_mcp_server_base_url(server_name)
    if base_url is None:
        raise MCPGatewayUpstreamError(
            code="unknown_server",
            message=f"Serveur MCP inconnu: {server_name}",
            details={"server_name": server_name},
        )

    url = f"{base_url}/rpc"
    timeout = httpx.Timeout(timeout_s, connect=min(5.0, timeout_s))

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=request_json, headers=headers)

        # ✅ Cas attendu: certains serveurs MCP (ex: fast-filesystem) renvoient
        # une 403 HTTP avec une charge utile JSON-RPC (PermissionError).
        # On doit forwarder la réponse JSON-RPC telle quelle, et laisser la
        # couche API décider du status HTTP final.
        if response.status_code not in {200, 403}:
            raise MCPGatewayUpstreamError(
                code="http_error",
                message=f"Réponse HTTP inattendue: {response.status_code}",
                details={"status_code": response.status_code, "body": response.text[:500]},
            )

        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise MCPGatewayUpstreamError(
                code="invalid_json",
                message="Réponse upstream non JSON",
                details={"status_code": response.status_code, "error": str(e), "body": response.text[:500]},
            )

    except httpx.TimeoutException as e:
        raise MCPGatewayUpstreamError(
            code="timeout",
            message="Timeout lors de l'appel au serveur MCP",
            details={"server_name": server_name, "url": url, "error": str(e)},
        )
    except httpx.ConnectError as e:
        raise MCPGatewayUpstreamError(
            code="connect_error",
            message="Erreur de connexion au serveur MCP",
            details={"server_name": server_name, "url": url, "error": str(e)},
        )


router = APIRouter()


# Observabilité (Phase 2D): métriques metadata-only, in-memory.
# Exposition optionnelle via /health (voir routes/health.py).
_MCP_TOOL_PRUNING_METRICS = MCPToolPruningMetricsCollector()

_CIRCUIT_BREAKERS: dict[str, MCPCircuitBreaker] = {}

def get_mcp_tool_pruning_metrics_collector() -> MCPToolPruningMetricsCollector:
    return _MCP_TOOL_PRUNING_METRICS


_GATEWAY_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
_GATEWAY_CACHE_TTL = 30.0

def _get_cache_key(server_name: str, request_json: dict[str, object]) -> str:
    raw = json.dumps(request_json, sort_keys=True)
    hash_str = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{server_name}:{hash_str}"

def _is_read_operation(request_json: dict[str, object]) -> bool:
    method = request_json.get("method")
    if method != "tools/call":
        return False
    params = request_json.get("params")
    if not isinstance(params, dict):
        return False
    name = params.get("name")
    if not isinstance(name, str):
        return False
    # Ecritures courantes
    if any(write_verb in name for write_verb in ("write", "edit", "create", "delete", "remove", "update")):
        return False
    return True


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


def _check_circuit_breaker(server_name: str, request_json: dict, request_json_obj: dict, service: MCPGatewayService) -> JSONResponse | None:
    try:
        config = get_mcp_gateway_config(get_config())
    except Exception:
        # Fallback défensif en cas d'erreur de config
        from ...core.constants import DEFAULT_MCP_CB_MAX_FAILURES, DEFAULT_MCP_CB_SIM_THRESHOLD, DEFAULT_MCP_CB_ENABLED
        config = MCPGatewayConfig(
            cb_enabled=DEFAULT_MCP_CB_ENABLED,
            cb_max_failures=DEFAULT_MCP_CB_MAX_FAILURES,
            cb_similarity_threshold=DEFAULT_MCP_CB_SIM_THRESHOLD
        )

    if not config.cb_enabled:
        return None

    if server_name not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[server_name] = MCPCircuitBreaker(
            max_failures=config.cb_max_failures,
            similarity_threshold=config.cb_similarity_threshold,
            enabled=config.cb_enabled
        )
    else:
        # Permettre le changement dynamique de configuration sans redémarrer le serveur
        cb = _CIRCUIT_BREAKERS[server_name]
        cb.max_failures = config.cb_max_failures
        cb.similarity_threshold = config.cb_similarity_threshold
        cb.enabled = config.cb_enabled

    cb = _CIRCUIT_BREAKERS[server_name]
    if request_json.get("method") == "tools/call":
        params = request_json.get("params")
        if isinstance(params, dict) and cb.check_call(params):
            error_payload = service.build_jsonrpc_error(
                request_json_obj,
                code=-32000,
                message="Circuit Breaker ouvert : Boucle d'appels MCP répétitifs détectée."
            )
            return JSONResponse(content=error_payload, status_code=429)
    return None

def _get_from_cache(server_name: str, request_json: dict) -> tuple[str | None, bool, JSONResponse | None]:
    is_read = _is_read_operation(request_json)
    cache_key = _get_cache_key(server_name, request_json) if is_read else None
    if is_read and cache_key in _GATEWAY_CACHE:
        ts, cached_resp = _GATEWAY_CACHE[cache_key]
        if time.time() - ts < _GATEWAY_CACHE_TTL:
            if isinstance(cached_resp, dict):
                cached_resp["_gateway_cached"] = True
            return cache_key, is_read, JSONResponse(content=cached_resp)
    return cache_key, is_read, None

def _update_cache(server_name: str, cache_key: str | None, is_read: bool, masked: dict):
    if is_read and cache_key:
        _GATEWAY_CACHE[cache_key] = (time.time(), masked)
    elif not is_read:
        prefix = f"{server_name}:"
        keys_to_del = [k for k in _GATEWAY_CACHE.keys() if k.startswith(prefix)]
        for k in keys_to_del:
            del _GATEWAY_CACHE[k]

async def _pruner_callable(*, request_id: int, text: str, goal_hint: str, source_type: SourceType, options: PruneOptionsDict, call_timeout_ms: int):
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
        return extract_prune_result_from_jsonrpc_response(resp)
    except Exception:
        return None

async def _apply_pruning(server_name: str, request_json: dict, upstream_response: dict) -> dict:
    try:
        toml_cfg = get_mcp_tool_pruning_config(get_config())
        pruning_cfg = resolve_mcp_tool_pruning_config(toml_cfg)
        return await maybe_prune_jsonrpc_response(
            server_name=server_name,
            request_json=request_json,
            response_json=upstream_response,
            cfg=pruning_cfg,
            pruner=_pruner_callable,
            metrics=_MCP_TOOL_PRUNING_METRICS,
        )
    except Exception:
        return upstream_response

def _handle_gateway_error(e: MCPGatewayUpstreamError, request_json: dict, service: MCPGatewayService) -> JSONResponse:
    if e.code == "unknown_server":
        code, status = -32001, 404
    elif e.code in {"timeout", "connect_error"}:
        code, status = -32002, 502
    elif e.code == "invalid_json":
        code, status = -32003, 502
    else:
        code, status = -32603, 502
    error_payload = service.build_jsonrpc_error(request_json, code=code, message=e.message, data=e.details)
    return JSONResponse(content=error_payload, status_code=status)

@router.post("/mcp-gateway/{server_name}/rpc")
async def api_mcp_gateway_rpc(server_name: str, request: Request):
    """Forwarde un JSON-RPC 2.0 brut vers un serveur MCP local puis masque la réponse."""
    service = MCPGatewayService()
    request_json_obj = await request.json()
    request_json = _as_dict(request_json_obj)
    
    if request_json is None:
        error_payload = service.build_jsonrpc_error(
            request_json_obj, code=-32600, message="Requête JSON-RPC invalide (attendu objet JSON)"
        )
        return JSONResponse(content=error_payload, status_code=400)

    cb_response = _check_circuit_breaker(server_name, request_json, request_json_obj, service)
    if cb_response: return cb_response

    cache_key, is_read, cached_response = _get_from_cache(server_name, request_json)
    if cached_response: return cached_response

    try:
        upstream_response = await forward_jsonrpc(server_name, request_json)
        pruned_response = await _apply_pruning(server_name, request_json, upstream_response)
        masked = service.mask_jsonrpc_response(pruned_response)
        _update_cache(server_name, cache_key, is_read, masked)
        return JSONResponse(content=masked)
    except MCPGatewayUpstreamError as e:
        return _handle_gateway_error(e, request_json, service)
