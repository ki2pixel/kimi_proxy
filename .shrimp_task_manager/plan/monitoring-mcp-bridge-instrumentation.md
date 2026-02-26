# Analyse — Points d’instrumentation (monitoring) dans `scripts/mcp_bridge.py`

Objectif: instrumenter **uniquement** les serveurs MCP en **stdio relay** (`filesystem-agent`, `ripgrep-agent`, `shrimp-task-manager`) pour compter/logguer les messages **JSON-RPC** sans jamais polluer `stdout`.

## Contraintes critiques

- `stdout` = **réservé au JSON-RPC** (déjà filtré). Aucune ligne de log/diagnostic ne doit y apparaître.
- Les bannières/logs du serveur child doivent continuer à être **redirigés vers `stderr`**.
- Monitoring **opt-in** uniquement (env var). Lorsque désactivé: comportement strictement inchangé.
- Ne pas exposer d’endpoint réseau dans le bridge pour cette itération.

## Sur quels flux observer ?

1) **Client → Server**

- Source: `stdin` du bridge (IDE/client)
- Destination: `proc.stdin` du serveur MCP (child)

2) **Server → Client**

- Source: `proc.stdout` du child
- Destination: `stdout` du bridge (IDE/client)

## Fonctions concernées et points d’accroche

### A) Stdio relay générique (filesystem-agent, ripgrep-agent)

Chemin: `main()` → `_run_stdio_relay(server_name)`.

#### 1. Client → Server

- Fonction actuelle: `_pipe_reader_to_writer_lines(reader, writer)`
- Utilisation:
  - `_run_stdio_relay()` crée `stdin_task = asyncio.create_task(_pipe_reader_to_writer_lines(...))`

Point d’accroche monitoring:

- **Juste après** `line = await reader.readline()` et **avant** `writer.write(line)`.
- Raison: observer le message côté bridge **sans** retarder le forwarding (best-effort).

Implémentation recommandée:

- Introduire un wrapper, ex: `_pipe_reader_to_writer_lines_with_monitor(reader, writer, monitor)`.

#### 2. Server → Client

- Fonction actuelle: `_pipe_child_stdout_jsonrpc_only(stream, stdout_buffer, stderr_buffer)`
- Utilisation:
  - `_run_stdio_relay()` crée `stdout_task = asyncio.create_task(_pipe_child_stdout_jsonrpc_only(...))`

Point d’accroche monitoring:

- Dans le bloc où la ligne est détectée comme candidate JSON (commence par `{`) et où `json.loads(...)` réussit.
- **Après** validation `candidate.get("jsonrpc") == "2.0"` et **juste avant** `stdout_buffer.write(line)`.
- Raison: on observe uniquement les objets JSON-RPC effectivement forwardés.

### B) Cas spécial shrimp-task-manager (roots/list shim)

Chemin: `main()` → `_run_stdio_relay("shrimp-task-manager")` → `_run_shrimp_task_manager_stdio_with_roots_shim()`.

#### 1. Client → Server

- Fonction: `_pump_client_to_server()`
- Comportement: appelle `_pipe_reader_to_writer_lines(reader=stdin_reader, writer=proc.stdin)`

Point d’accroche:

- Même stratégie que stdio relay générique: wrapper pipe avec monitoring.

#### 2. Server → Client (avec interception roots/list)

- Fonction: `_pump_server_to_client_with_shim()`
- Logique:
  - lit `line = await proc.stdout.readline()`
  - parse `msg_obj = json.loads(...)` (best-effort)
  - si `msg_obj` est une **requête JSON-RPC** et `method == "roots/list"`: fabriquer une réponse `roots_payload` et l’écrire sur `proc.stdin` (reply au serveur)
  - sinon: si dict JSON-RPC, forward vers `sys.stdout.buffer`
  - sinon: rediriger vers `stderr`

Points d’accroche:

1) **Observation de la requête `roots/list`**
   - Après parsing `msg_obj` et avant `continue`.
2) **Observation de la réponse shim `roots_payload`**
   - Juste avant `proc.stdin.write(...)` (ou juste après `await proc.stdin.drain()`), mais sans bloquer.
3) **Observation des messages JSON-RPC forwardés (non roots/list)**
   - Juste avant `sys.stdout.buffer.write(line)`.

## Classification JSON-RPC à compter/logguer (best-effort)

Sur un objet JSON-RPC (`jsonrpc == "2.0"`):

- Si `method` est présent: **request/notification** (compter par `method`).
- Si `result` ou `error` est présent: **response** (compter total réponses).

Nota: ne pas logguer `params`, ni `result` (metadata uniquement).

## Proposition d’événement minimal (JSONL)

Champs proposés:

- `ts`: ISO 8601 UTC
- `server`: nom du serveur (filesystem-agent/ripgrep-agent/shrimp-task-manager)
- `direction`: `client_to_server` | `server_to_client`
- `kind`: `request` | `response`
- `method`: string (optionnel, si request)
- `id`: JSON scalar/object (optionnel)
- `dropped`: bool (optionnel, pour signaler drop queue/backpressure)

## Variables d’environnement (activation)

- `MCP_BRIDGE_MONITORING_ENABLED=1` (default 0)
- `MCP_BRIDGE_MONITORING_LOG_PATH=/path/to/log.jsonl` (optionnel)
- `MCP_BRIDGE_MONITORING_QUEUE_MAX=1000` (optionnel)
- `MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT=1` (optionnel)
