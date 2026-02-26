# MCP Bridge (stdio) pour Continue/Cline/Windsurf

**TL;DR**: si un serveur MCP stdio (filesystem-agent, ripgrep-agent, shrimp-task-manager) écrit des bannières/logs sur stdout, Continue/Cline peuvent casser le parsing JSON-RPC. `scripts/mcp_bridge.py` sert de “shim” pour relayer stdin/stdout et filtrer stdout afin de ne laisser passer que du JSON-RPC.

## Le problème

Continue/Cline attendent un flux JSON-RPC 2.0 sur stdout. Or certains serveurs MCP stdio impriment au démarrage des messages du type:

```text
Secure MCP Filesystem Server running on stdio
Ripgrep MCP Server running
```

Ces lignes ne sont pas du JSON-RPC; elles corrompent le flux.

Un second problème peut apparaître avec **ripgrep-agent**: certaines réponses JSON-RPC sont **très volumineuses** (ex: beaucoup de matches). Par défaut, `asyncio` impose une limite interne (~64KiB) sur `StreamReader.readline()`. Si une réponse dépasse cette limite, la lecture stdout peut échouer et l’IDE finit par remonter un timeout / erreur JSON-RPC (souvent `-32001`).

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

En plus, le bridge:

- augmente la limite de lecture des flux stdio via `MCP_BRIDGE_STDIO_STREAM_LIMIT` (défaut: 8MiB, clamp 64KiB–64MiB)
- suit les IDs JSON-RPC “inflight” (best-effort) pour pouvoir **répondre immédiatement** avec une erreur `-32001` si la lecture stdout échoue (plutôt que laisser l’IDE timeout)

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
      MCP_BRIDGE_STDIO_STREAM_LIMIT: "8388608"  # 8 MiB
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

## Monitoring (opt-in) des requêtes JSON-RPC

**TL;DR**: tu peux activer un monitoring simple (compteurs + logs JSONL) **sans jamais polluer stdout**; tout se fait via variables d’environnement.

### Quand l’activer

Tu l’actives quand tu veux répondre à des questions du type:

- "Est-ce que mon IDE envoie bien `tools/list` ?"
- "Quel outil est spammé ?"
- "Est-ce que j’ai des erreurs JSON-RPC côté serveur ?"

Par défaut, c’est désactivé; le comportement du bridge reste inchangé.

### Ce que ça enregistre

- **Requêtes**: comptées par `method` (ex: `tools/list`, `tools/call`)
- **Réponses**: total + total erreurs
- **Logs JSONL** (optionnel): une ligne JSON par événement, metadata uniquement

Champs JSONL:

- `ts`: ISO 8601 UTC
- `server`: `filesystem-agent` | `ripgrep-agent` | `shrimp-task-manager`
- `direction`: `client_to_server` | `server_to_client`
- `kind`: `request` | `response`
- `method`: présent uniquement pour `kind=request`
- `id`: présent si fourni par le message JSON-RPC

### ❌ Ce que ça ne loggue jamais

- `params` (risque de fuite, peut être volumineux)
- `result` / `error` (peut être sensible ou très gros)

### Activation (exemple)

Dans ta config IDE, ajoute simplement ces variables d’environnement au serveur:

```yaml
env:
  MCP_BRIDGE_MONITORING_ENABLED: "1"
  MCP_BRIDGE_MONITORING_LOG_PATH: "/tmp/kimi-proxy/mcp-bridge-filesystem.jsonl"
  MCP_BRIDGE_MONITORING_QUEUE_MAX: "1000"
  MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT: "1"
```

Notes:

- Le fichier est en **append**.
- Le résumé (JSON) est écrit sur **stderr** à l’arrêt, jamais sur stdout.

### Trade-offs

| Option | Avantage | Inconvénient |
|---|---|---|
| Compteurs uniquement | Zéro I/O disque | Moins pratique pour analyser a posteriori |
| JSONL (fichier) | Très simple à greper/jq | Volume disque; rotation non gérée ici |

## Variables d’environnement supportées

### Commun

- `MCP_GATEWAY_BASE_URL` (défaut: `http://localhost:8000`)
- `MCP_BRIDGE_PATH_ENV` (si défini, remplace `PATH` du sous-processus)
- `MCP_BRIDGE_MONITORING_ENABLED` (défaut: `0`)
- `MCP_BRIDGE_MONITORING_LOG_PATH` (optionnel; active l’écriture JSONL)
- `MCP_BRIDGE_MONITORING_QUEUE_MAX` (défaut: `1000`)
- `MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT` (défaut: `1` si monitoring activé)
- `MCP_BRIDGE_STDIO_STREAM_LIMIT` (défaut: `8388608` = 8MiB; clamp 64KiB–64MiB)

### filesystem-agent

- `MCP_FILESYSTEM_ALLOWED_ROOT` (défaut: `/home/kidpixel`)
- `MCP_FILESYSTEM_COMMAND` (défaut: `npx`)

### ripgrep-agent

- `MCP_RIPGREP_COMMAND` (défaut: `npx`)

### shrimp-task-manager

- `MCP_SHRIMP_TASK_MANAGER_COMMAND` (défaut: `/home/kidpixel/.local/bin/shrimp-task-manager` si présent, sinon `shrimp-task-manager`)

## Golden Rule

Le bridge ne doit jamais écrire de logs sur stdout. Tout ce qui n’est pas JSON-RPC doit aller sur stderr.

## Runbook: ripgrep-agent timeout / erreur `-32001`

**TL;DR**: si tu vois des timeouts ripgrep-agent, c’est souvent une réponse trop grosse sur une seule ligne.

1) **Borne la requête** côté client: réduis `maxResults`, utilise un pattern plus précis, ou scinde la recherche.
2) **Augmente la limite** côté bridge: `MCP_BRIDGE_STDIO_STREAM_LIMIT=8388608` (ou plus si nécessaire).
3) **Vérifie les logs**:
   - stderr du bridge: tu dois voir un message du type `stdout relay error ... chunk exceed the limit`
   - JSONL monitoring (si activé): `/tmp/kimi-proxy/mcp-bridge-ripgrep.jsonl`

Si malgré ça tu retombes sur des réponses massives, préfère un fallback shell (`rg ...`) pour limiter la taille des retours, puis affine.
