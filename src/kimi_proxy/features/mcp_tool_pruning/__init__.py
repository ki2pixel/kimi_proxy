"""kimi_proxy.features.mcp_tool_pruning

Pruning conditionnel des outputs de `tools/call` pour les serveurs MCP, sans changer
les contrats JSON-RPC exposés côté IDE.

Ce package fournit:
- un moteur (sans I/O) pour réécrire une réponse JSON-RPC en ne modifiant que
  certains champs string;
- des helpers de construction/parsing pour appeler le serveur MCP pruner.

L'I/O réseau (httpx) doit rester dans la couche Proxy ou dans `scripts/`.
"""

from .engine import (
    MCPToolPruningResolvedConfig,
    PrunerCallable,
    maybe_prune_jsonrpc_response,
    resolve_mcp_tool_pruning_config,
)

from .metrics import MCPToolPruningMetricsCollector, MCPToolPruningMetricsSnapshot

__all__ = [
    "MCPToolPruningResolvedConfig",
    "PrunerCallable",
    "maybe_prune_jsonrpc_response",
    "resolve_mcp_tool_pruning_config",
    "MCPToolPruningMetricsCollector",
    "MCPToolPruningMetricsSnapshot",
]
