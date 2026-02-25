#!/usr/bin/env python3
"""scripts.mcp_bridge

MCP Bridge.

Ce script fournit un point d’entrée unique côté IDE (Continue/Cline/Windsurf):

    python3 scripts/mcp_bridge.py <server_name>

Deux modes selon le serveur:

- gateway-http:
    Lit des messages JSON-RPC (1 message par ligne) sur stdin et les forwarde
    vers le MCP Gateway HTTP:
        {MCP_GATEWAY_BASE_URL}/api/mcp-gateway/{server_name}/rpc

- stdio-relay:
    Lance un serveur MCP en stdio (sous-processus) et relaie stdin→child.stdin
    et child.stdout→stdout.

Important:
- Le bridge ne doit jamais écrire de logs sur stdout (sinon corruption JSON-RPC).
- En mode relay, ce script n’interprète pas le JSON-RPC: il relaie le flux.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx


GATEWAY_HTTP_SERVERS: frozenset[str] = frozenset(
    {
        "context-compression",
        "sequential-thinking",
        "fast-filesystem",
        "json-query",
    }
)

STDIO_RELAY_SERVERS: frozenset[str] = frozenset(
    {
        "filesystem-agent",
        "ripgrep-agent",
        "shrimp-task-manager",
    }
)


@dataclass(frozen=True)
class RelayCommand:
    command: str
    args: list[str]
    env: dict[str, str]


def _jsonrpc_error(*, code: int, message: str, req_id: object | None) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "error": {"code": int(code), "message": message},
        "id": req_id,
    }


def _extract_jsonrpc_id(request_obj: object) -> object | None:
    if isinstance(request_obj, dict) and "id" in request_obj:
        return request_obj.get("id")
    return None


def _is_jsonrpc_request_message(obj: object) -> bool:
    return isinstance(obj, dict) and obj.get("jsonrpc") == "2.0" and isinstance(obj.get("method"), str)


def _build_roots_list_result(*, req_id: object | None, root_path: Path) -> dict[str, object]:
    # MCP "roots/list" response shape: { roots: [{ uri, name? }] }
    # We always return a file:// root so servers can derive workspace paths.
    try:
        uri = root_path.resolve().as_uri()
    except Exception:
        # Best-effort fallback; as_uri() needs absolute path.
        uri = Path.cwd().resolve().as_uri()

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "roots": [
                {
                    "uri": uri,
                    "name": "workspace",
                }
            ]
        },
    }


def _get_workspace_root_for_roots_list() -> Path:
    # Prefer explicit env, then the same WORKSPACE_PATH convention used elsewhere,
    # otherwise fall back to the current working directory.
    env_root = os.getenv("MCP_WORKSPACE_ROOT") or os.getenv("WORKSPACE_PATH")
    if env_root:
        try:
            return Path(env_root).expanduser().resolve(strict=False)
        except Exception:
            return Path.cwd().resolve()
    return Path.cwd().resolve()


def _get_gateway_url(server_name: str) -> str:
    base = os.getenv("MCP_GATEWAY_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/api/mcp-gateway/{server_name}/rpc"


def _get_default_path_env() -> str:
    # Valeur observée dans config.yaml (Continue.dev)
    return "/usr/bin:/bin:/usr/local/bin"


def _base_relay_env() -> dict[str, str]:
    env = dict(os.environ)

    # Permet d’imposer un PATH minimal/contrôlé pour les sous-processus.
    if "MCP_BRIDGE_PATH_ENV" in os.environ:
        env["PATH"] = os.environ["MCP_BRIDGE_PATH_ENV"]

    return env


def _build_filesystem_agent_command() -> RelayCommand:
    allowed_root = os.getenv("MCP_FILESYSTEM_ALLOWED_ROOT", "/home/kidpixel")
    cmd = os.getenv("MCP_FILESYSTEM_COMMAND", "npx")
    args = ["-y", "@modelcontextprotocol/server-filesystem", allowed_root]

    env = _base_relay_env()
    env.setdefault("PATH", _get_default_path_env())

    return RelayCommand(command=cmd, args=args, env=env)


def _build_ripgrep_agent_command() -> RelayCommand:
    cmd = os.getenv("MCP_RIPGREP_COMMAND", "npx")
    args = ["-y", "mcp-ripgrep"]

    env = _base_relay_env()
    env.setdefault("PATH", _get_default_path_env())

    return RelayCommand(command=cmd, args=args, env=env)


def _build_shrimp_task_manager_command() -> RelayCommand:
    default_path = "/home/kidpixel/.local/bin/shrimp-task-manager"
    default_cmd = default_path if Path(default_path).exists() else "shrimp-task-manager"
    cmd = os.getenv("MCP_SHRIMP_TASK_MANAGER_COMMAND", default_cmd)

    env = _base_relay_env()

    return RelayCommand(command=cmd, args=[], env=env)


def _build_stdio_relay_command(server_name: str) -> RelayCommand:
    if server_name == "filesystem-agent":
        return _build_filesystem_agent_command()
    if server_name == "ripgrep-agent":
        return _build_ripgrep_agent_command()
    if server_name == "shrimp-task-manager":
        return _build_shrimp_task_manager_command()

    raise ValueError(f"Serveur stdio-relay non supporté: {server_name}")


async def _connect_stdin_reader() -> asyncio.StreamReader:
    """Retourne un StreamReader non-bloquant connecté à stdin (binaire)."""

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
    return reader


async def _pipe_reader_to_writer_lines(*, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    while True:
        line = await reader.readline()
        if not line:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        writer.write(line)
        await writer.drain()


async def _pipe_stream_to_buffer_lines(*, stream: asyncio.StreamReader, out, flush: bool) -> None:
    while True:
        line = await stream.readline()
        if not line:
            return
        out.write(line)
        if flush:
            out.flush()


async def _pipe_child_stdout_jsonrpc_only(
    *,
    stream: asyncio.StreamReader,
    stdout_buffer,
    stderr_buffer,
) -> None:
    """Relaye uniquement les lignes JSON (objets) vers stdout.

    Certains serveurs MCP stdio (ex: server-filesystem) peuvent imprimer une bannière
    ou des logs sur stdout au démarrage. Cela corrompt le flux JSON-RPC côté client.

    Stratégie:
    - si la ligne (après strip gauche) commence par '{' => forward vers stdout
    - sinon => rediriger vers stderr (best-effort)
    """

    while True:
        line = await stream.readline()
        if not line:
            return

        stripped_left = line.lstrip()
        if stripped_left.startswith(b"{"):
            # Filtre minimal anti-logs JSON:
            # on ne forwarde que des objets JSON-RPC {"jsonrpc": "2.0", ...}
            try:
                candidate = json.loads(stripped_left.decode("utf-8", errors="replace"))
                if isinstance(candidate, dict) and candidate.get("jsonrpc") == "2.0":
                    stdout_buffer.write(line)
                    stdout_buffer.flush()
                    continue
            except json.JSONDecodeError:
                pass

        # Ne jamais écrire de logs sur stdout.
        try:
            stderr_buffer.write(b"[mcp_bridge relay stdout] " + line)
            stderr_buffer.flush()
        except Exception:
            pass


async def _run_shrimp_task_manager_stdio_with_roots_shim() -> int:
    """Run shrimp-task-manager stdio server with a client-side shim for roots/list.

    Some MCP servers (notably Shrimp Task Manager) call `roots/list` as a request
    FROM server -> client to discover workspace roots. Some IDE clients support
    this bidirectionally; a plain stdin/stdout pipe does not.

    This shim:
    - forwards client->server messages as-is
    - intercepts server->client `roots/list` requests and replies with a file:// root
      derived from the current working directory.

    This keeps Continue.dev behavior while allowing other clients to work.
    """

    relay_cmd = _build_shrimp_task_manager_command()
    stdin_reader = await _connect_stdin_reader()

    try:
        proc = await asyncio.create_subprocess_exec(
            relay_cmd.command,
            *relay_cmd.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=relay_cmd.env,
        )
    except Exception as e:
        # Mirror behavior from _run_stdio_relay: answer errors for every incoming request.
        while True:
            raw = await stdin_reader.readline()
            if not raw:
                return 1

            try:
                req_obj = json.loads(raw.decode("utf-8", errors="replace").strip())
                req_id = _extract_jsonrpc_id(req_obj)
            except json.JSONDecodeError:
                req_id = None

            payload = _jsonrpc_error(
                code=-32603,
                message=f"Impossible de démarrer shrimp-task-manager: {e}",
                req_id=req_id,
            )
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    async def _pump_client_to_server() -> None:
        await _pipe_reader_to_writer_lines(reader=stdin_reader, writer=proc.stdin)  # type: ignore[arg-type]

    async def _pump_server_to_client_with_shim() -> None:
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    return

                stripped_left = line.lstrip()
                if stripped_left.startswith(b"{"):
                    try:
                        msg_obj = json.loads(stripped_left.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        msg_obj = None

                    if _is_jsonrpc_request_message(msg_obj) and msg_obj.get("method") == "roots/list":
                        req_id = _extract_jsonrpc_id(msg_obj)
                        roots_payload = _build_roots_list_result(
                            req_id=req_id,
                            root_path=_get_workspace_root_for_roots_list(),
                        )
                        # Reply to server on its stdin
                        try:
                            proc.stdin.write(
                                (json.dumps(roots_payload, ensure_ascii=False) + "\n").encode("utf-8")
                            )
                            await proc.stdin.drain()
                        except (BrokenPipeError, ConnectionResetError):
                            return
                        continue

                    # Default filtering policy: only forward JSON-RPC objects.
                    if isinstance(msg_obj, dict) and msg_obj.get("jsonrpc") == "2.0":
                        sys.stdout.buffer.write(line)
                        sys.stdout.buffer.flush()
                        continue

                # Anything else is considered logs/banners; redirect to stderr.
                try:
                    sys.stderr.buffer.write(b"[mcp_bridge relay stdout] " + line)
                    sys.stderr.buffer.flush()
                except Exception:
                    pass
        except asyncio.CancelledError:
            return

    stdin_task = asyncio.create_task(_pump_client_to_server())
    stdout_task = asyncio.create_task(_pump_server_to_client_with_shim())
    stderr_task = asyncio.create_task(_pipe_stream_to_buffer_lines(stream=proc.stderr, out=sys.stderr.buffer, flush=True))
    proc_wait_task = asyncio.create_task(proc.wait())

    done, _pending = await asyncio.wait(
        {stdin_task, proc_wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if proc_wait_task in done and not stdin_task.done():
        stdin_task.cancel()
        try:
            await stdin_task
        except asyncio.CancelledError:
            pass

    if stdin_task in done and not proc_wait_task.done():
        try:
            await asyncio.wait_for(proc_wait_task, timeout=2.0)
        except asyncio.TimeoutError:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await proc_wait_task
            except asyncio.CancelledError:
                pass

    returncode = int(proc.returncode or 0)

    for task in (stdout_task, stderr_task):
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return returncode


async def _run_stdio_relay(server_name: str) -> int:
    # Special-case: shrimp-task-manager uses bidirectional requests (roots/list).
    if server_name == "shrimp-task-manager":
        return await _run_shrimp_task_manager_stdio_with_roots_shim()

    relay_cmd = _build_stdio_relay_command(server_name)
    stdin_reader = await _connect_stdin_reader()

    try:
        proc = await asyncio.create_subprocess_exec(
            relay_cmd.command,
            *relay_cmd.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=relay_cmd.env,
        )
    except Exception as e:
        # Si le process ne démarre pas, répondre en JSON-RPC à chaque requête reçue
        # pour rendre l’erreur visible côté client.
        while True:
            raw = await stdin_reader.readline()
            if not raw:
                return 1

            try:
                req_obj = json.loads(raw.decode("utf-8", errors="replace").strip())
                req_id = _extract_jsonrpc_id(req_obj)
            except json.JSONDecodeError:
                req_id = None

            payload = _jsonrpc_error(
                code=-32603,
                message=f"Impossible de démarrer {server_name}: {e}",
                req_id=req_id,
            )
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdin_task = asyncio.create_task(
        _pipe_reader_to_writer_lines(reader=stdin_reader, writer=proc.stdin)
    )
    stdout_task = asyncio.create_task(
        _pipe_child_stdout_jsonrpc_only(
            stream=proc.stdout,
            stdout_buffer=sys.stdout.buffer,
            stderr_buffer=sys.stderr.buffer,
        )
    )
    stderr_task = asyncio.create_task(
        _pipe_stream_to_buffer_lines(stream=proc.stderr, out=sys.stderr.buffer, flush=True)
    )
    proc_wait_task = asyncio.create_task(proc.wait())

    done, _pending = await asyncio.wait(
        {stdin_task, proc_wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Si le process se termine alors que stdin reste ouvert, on arrête la lecture.
    if proc_wait_task in done and not stdin_task.done():
        stdin_task.cancel()
        try:
            await stdin_task
        except asyncio.CancelledError:
            pass

    # Si stdin est fermé, on tente d’arrêter proprement le process (s’il tourne encore)
    if stdin_task in done and not proc_wait_task.done():
        try:
            await asyncio.wait_for(proc_wait_task, timeout=2.0)
        except asyncio.TimeoutError:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            await proc_wait_task

    returncode = int(proc.returncode or 0)

    # Laisse stdout/stderr se vider (EOF). Ne cancel qu'en dernier recours.
    for task in (stdout_task, stderr_task):
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return returncode


async def _run_gateway_http(server_name: str) -> int:
    gateway_url = _get_gateway_url(server_name)
    stdin_reader = await _connect_stdin_reader()

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            raw = await stdin_reader.readline()
            if not raw:
                return 0

            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue

            try:
                request_obj = json.loads(line)
            except json.JSONDecodeError:
                payload = _jsonrpc_error(code=-32700, message="Parse error", req_id=None)
                sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
                sys.stdout.flush()
                continue

            req_id = _extract_jsonrpc_id(request_obj)

            try:
                response = await client.post(gateway_url, json=request_obj)
                response_obj: object = response.json()
                sys.stdout.write(json.dumps(response_obj, ensure_ascii=False) + "\n")
                sys.stdout.flush()
            except Exception as e:
                payload = _jsonrpc_error(code=-32603, message=str(e), req_id=req_id)
                sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
                sys.stdout.flush()


async def main() -> None:
    if len(sys.argv) != 2:
        payload = _jsonrpc_error(
            code=-32602,
            message="Invalid params: server name required",
            req_id=None,
        )
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return

    server_name = sys.argv[1]

    if server_name in GATEWAY_HTTP_SERVERS:
        await _run_gateway_http(server_name)
        return

    if server_name in STDIO_RELAY_SERVERS:
        await _run_stdio_relay(server_name)
        return

    payload = _jsonrpc_error(
        code=-32602,
        message=f"Invalid params: unknown server '{server_name}'",
        req_id=None,
    )
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
