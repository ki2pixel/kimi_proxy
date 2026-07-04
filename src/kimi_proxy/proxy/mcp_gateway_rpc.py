"""kimi_proxy.proxy.mcp_gateway_rpc — Stub de rétro-compatibilité.

Ce module ré-exporte les symboles consolidés dans
``kimi_proxy.api.routes.mcp_gateway`` pour maintenir la compatibilité
des imports existants (ex: ``context_pruning.py``).

TODO(audit): supprimer ce fichier une fois que tous les consommateurs
auront migré vers l'import canonical.
"""

from __future__ import annotations

# Re-export canonique
from ..api.routes.mcp_gateway import (  # noqa: F401
    MCPGatewayUpstreamError,
    forward_jsonrpc,
    get_mcp_server_base_url,
)

__all__ = [
    "MCPGatewayUpstreamError",
    "forward_jsonrpc",
    "get_mcp_server_base_url",
]
