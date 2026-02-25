# Brief — Déboguer les connexions MCP (Windsurf / Cline / Continue.dev)

## Objectif

Rendre **filesystem-agent**, **ripgrep-agent** et **shrimp-task-manager** utilisables de façon fiable dans :

- Windsurf (config: `mcp_config.json`)
- Cline (config: `cline_mcp_settings.json`)
- Continue.dev (config: `config.yaml`)

Sans casser le fonctionnement existant de Continue.dev.

## Constat (état actuel)

1) Continue.dev fonctionne car il lance les serveurs **stdio** via `scripts/mcp_bridge.py`.
2) Kimi Proxy expose un **MCP Gateway HTTP** (`/api/mcp-gateway/{server}/rpc`) qui ne mappe que :

- `context-compression` → `http://127.0.0.1:8001/rpc`
- `sequential-thinking` → `http://127.0.0.1:8003/rpc`
- `fast-filesystem` → `http://127.0.0.1:8004/rpc`
- `json-query` → `http://127.0.0.1:8005/rpc`

3) Donc, quand Windsurf/Cline pointent `filesystem-agent`, `ripgrep-agent` ou `shrimp-task-manager` vers le gateway HTTP,
le gateway répond : **"Serveur MCP inconnu"** (JSON-RPC error `-32001`, HTTP 404).

## Exigences

- Les noms de serveurs doivent être identiques entre outils.
- Continuer à utiliser le gateway HTTP pour les serveurs HTTP (sequential-thinking / fast-filesystem / json-query).
- Utiliser **stdio + bridge** pour les serveurs stdio:
  - `filesystem-agent`
  - `ripgrep-agent`
  - `shrimp-task-manager`
- Ne pas introduire de routes de compatibilité supplémentaires côté API.

## Implémentation proposée (interop)

### Continue.dev (référence)

Conserver `config.yaml` tel quel:

- `command: python3`
- `args: ["/home/kidpixel/kimi-proxy/scripts/mcp_bridge.py", "<server>"]`

### Cline

Dans `cline_mcp_settings.json`, basculer ces 3 serveurs en **stdio** via `command/args/env`, plutôt que `url`.

### Windsurf

Dans `mcp_config.json`, basculer ces 3 serveurs en **stdio** via `command/args/env`, plutôt que `serverUrl`.

## Tests & validation

1) Vérifier que Kimi Proxy est UP: `curl http://127.0.0.1:8000/health`
2) Vérifier que les serveurs HTTP répondent via gateway: initialize OK pour `sequential-thinking`, `fast-filesystem`, `json-query`.
3) Vérifier que les serveurs stdio répondent via bridge:

```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}' \
  | python3 scripts/mcp_bridge.py filesystem-agent
```

Répéter pour `ripgrep-agent` et `shrimp-task-manager`.

4) Re-tester dans Windsurf et Cline.

## Risques

- Variables d’environnement (PATH / root autorisé) doivent être cohérentes entre IDEs.
- Sur certaines machines, `npx` peut être absent du PATH si l’IDE n’hérite pas du shell : imposer `PATH` minimal via `MCP_BRIDGE_PATH_ENV`.
