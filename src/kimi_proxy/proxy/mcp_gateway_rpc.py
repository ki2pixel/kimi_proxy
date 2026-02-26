"""kimi_proxy.proxy.mcp_gateway_rpc

Forwarding JSON-RPC brut vers les serveurs MCP locaux (HTTP /rpc).

Couche Proxy:
- Contient l'I/O HTTP (httpx.AsyncClient)
- Ne reconstruit pas les payloads JSON-RPC (préserve `id` et la structure)
"""

from __future__ import annotations

from dataclasses import dataclass
import json

import httpx


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
