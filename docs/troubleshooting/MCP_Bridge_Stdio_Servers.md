# MCP Bridge (stdio) pour Continue/Cline/Windsurf

**TL;DR**: si un serveur MCP stdio (filesystem-agent, ripgrep-agent, shrimp-task-manager) écrit des bannières/logs sur stdout, Continue/Cline peuvent casser le parsing JSON-RPC. `scripts/mcp_bridge.py` sert de “shim” pour relayer stdin/stdout et filtrer stdout afin de ne laisser passer que du JSON-RPC.

## Le problème

Continue/Cline attendent un flux JSON-RPC 2.0 sur stdout. Or certains serveurs MCP stdio impriment au démarrage des messages du type:

```text
Secure MCP Filesystem Server running on stdio
Ripgrep MCP Server running
```

Ces lignes ne sont pas du JSON-RPC; elles corrompent le flux.

## La solution: `scripts/mcp_bridge.py`

Ce script supporte deux modes:

1) `gateway-http` pour les serveurs MCP HTTP exposés via Kimi Proxy:

```text
{MCP_GATEWAY_BASE_URL}/api/mcp-gateway/{server}/rpc
```

2) `stdio-relay` pour les serveurs MCP stdio:
- lance le serveur en sous-processus
- relaye `stdin -> child.stdin`
- filtre `child.stdout -> stdout` et ne forwarde que les objets JSON-RPC (avec `"jsonrpc": "2.0"`)
- redirige tout le reste vers stderr

## Exemple de configuration (sans secrets)

Dans `config.yaml` (Continue.dev), vous pouvez lancer les serveurs stdio via le bridge.

### filesystem-agent

```yaml
mcpServers:
  - name: filesystem-agent
    command: python3
    args: ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "filesystem-agent"]
    env:
      MCP_FILESYSTEM_ALLOWED_ROOT: "/home/kidpixel"
      MCP_BRIDGE_PATH_ENV: "/usr/bin:/bin:/usr/local/bin"
      PATH: "/usr/bin:/bin:/usr/local/bin"
```

### ripgrep-agent

```yaml
  - name: ripgrep-agent
    command: python3
    args: ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "ripgrep-agent"]
    env:
      MCP_BRIDGE_PATH_ENV: "/usr/bin:/bin:/usr/local/bin"
      PATH: "/usr/bin:/bin:/usr/local/bin"
```

### shrimp-task-manager

```yaml
  - name: shrimp-task-manager
    command: python3
    args: ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "shrimp-task-manager"]
    env:
      MCP_SHRIMP_TASK_MANAGER_COMMAND: "/home/kidpixel/.local/bin/shrimp-task-manager"
      MCP_BRIDGE_PATH_ENV: "/usr/bin:/bin:/usr/local/bin"
      PATH: "/usr/bin:/bin:/usr/local/bin"
```

## Shim Bidirectional pour Roots/List

Certains serveurs MCP stdio, notamment Shrimp Task Manager, appellent `roots/list` comme requête du serveur vers le client pour découvrir les racines workspace. Puisque le bridge utilise un pipe stdio unidirectionnel, il ne peut pas gérer les requêtes bidirectionnelles.

Le shim intercepte les requêtes server→client `roots/list` et répond automatiquement avec une racine `file://` dérivée du répertoire de travail courant ou de `MCP_WORKSPACE_ROOT`.

Voir le code dans `_run_shrimp_task_manager_stdio_with_roots_shim` dans `scripts/mcp_bridge.py`.

Cela permet à Continue.dev et autres clients de fonctionner sans support bidirectionnel natif.

## Variables d’environnement supportées

### Commun

- `MCP_GATEWAY_BASE_URL` (défaut: `http://localhost:8000`)
- `MCP_BRIDGE_PATH_ENV` (si défini, remplace `PATH` du sous-processus)

### filesystem-agent

- `MCP_FILESYSTEM_ALLOWED_ROOT` (défaut: `/home/kidpixel`)
- `MCP_FILESYSTEM_COMMAND` (défaut: `npx`)

### ripgrep-agent

- `MCP_RIPGREP_COMMAND` (défaut: `npx`)

### shrimp-task-manager

- `MCP_SHRIMP_TASK_MANAGER_COMMAND` (défaut: `/home/kidpixel/.local/bin/shrimp-task-manager` si présent, sinon `shrimp-task-manager`)

## Golden Rule

Le bridge ne doit jamais écrire de logs sur stdout. Tout ce qui n’est pas JSON-RPC doit aller sur stderr.
