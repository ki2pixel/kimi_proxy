# Pruner MCP Server (local HTTP)

Ce répertoire fournit un point d’entrée simple pour démarrer le serveur MCP **Pruner**.

## Démarrage

```bash
python3 -m kimi_proxy.features.mcp_pruner.server
```

Variables d’environnement:

- `MCP_PRUNER_HOST` (défaut: `0.0.0.0`)
- `MCP_PRUNER_PORT` (défaut: `8006`)
- `MCP_PRUNER_MAX_INPUT_CHARS` (défaut: `2000000`)
- `MCP_PRUNER_PRUNE_ID_TTL_S` (défaut: `600`)

## Contrat

Voir:

- `docs/features/mcp-pruner.md`
- `src/kimi_proxy/features/mcp_pruner/spec.py`
