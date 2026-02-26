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
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Literal

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


Direction = Literal["client_to_server", "server_to_client"]
EventKind = Literal["request", "response"]


@dataclass(frozen=True)
class BridgeMonitorEvent:
    ts: str
    server: str
    direction: Direction
    kind: EventKind
    method: str | None
    req_id: object | None

    def to_json_line(self) -> str:
        payload: dict[str, object] = {
            "ts": self.ts,
            "server": self.server,
            "direction": self.direction,
            "kind": self.kind,
        }
        if self.method is not None:
            payload["method"] = self.method
        if self.req_id is not None:
            payload["id"] = self.req_id
        return json.dumps(payload, ensure_ascii=False)


def _now_utc_iso() -> str:
    # ISO 8601 UTC with ms precision, 'Z' suffix.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _get_stdio_stream_limit_bytes() -> int:
    """Taille max (en bytes) d'une "ligne" lue depuis stdout/stderr des serveurs stdio.

    Contexte:
    - Le bridge lit stdout via StreamReader.readline().
    - asyncio applique une limite interne (par défaut 65536 bytes).
    - Certains serveurs (ex: mcp-ripgrep) peuvent renvoyer une réponse JSON-RPC très
      volumineuse sur une seule ligne, ce qui peut déclencher un LimitOverrunError.

    On expose donc une config via env pour augmenter cette limite.
    """

    # Défaut volontairement supérieur à 64KiB pour éviter les timeouts "silencieux",
    # tout en restant raisonnable en mémoire.
    default_limit = 8 * 1024 * 1024  # 8 MiB
    min_limit = 64 * 1024
    max_limit = 64 * 1024 * 1024  # 64 MiB

    configured = _env_int("MCP_BRIDGE_STDIO_STREAM_LIMIT", default=default_limit)
    if configured <= 0:
        return default_limit
    return min(max_limit, max(min_limit, configured))


def _safe_jsonrpc_id(req_id: object | None) -> str | int | float | None:
    # JSON-RPC 2.0: id is string | number | null.
    if req_id is None:
        return None
    if isinstance(req_id, (str, int, float)):
        return req_id
    return None


class InflightTracker:
    """Track best-effort JSON-RPC request IDs in flight.

    Objectif:
    - Si le relay stdout crash (limit overrun, EOF inattendu, etc.), renvoyer
      immédiatement des erreurs JSON-RPC pour éviter un timeout côté IDE.

    Notes:
    - On ne stocke que les IDs hashables (str/int/float).
    - On borne la taille pour éviter une croissance sans limite en cas de client
      défaillant.
    """

    def __init__(self, *, max_inflight: int = 2048) -> None:
        self._max_inflight = max(1, int(max_inflight))
        self._inflight: set[str | int | float] = set()

    def observe_client_message(self, obj: object) -> None:
        # Support minimal des batchs JSON-RPC (liste de requêtes).
        if isinstance(obj, list):
            for item in obj:
                self.observe_client_message(item)
            return

        if not _is_jsonrpc_request_message(obj):
            return

        req_id = _safe_jsonrpc_id(obj.get("id")) if isinstance(obj, dict) else None
        if req_id is None:
            return

        if len(self._inflight) >= self._max_inflight:
            # Best-effort: si trop d'IDs, on reset pour éviter OOM.
            self._inflight.clear()
        self._inflight.add(req_id)

    def observe_server_message(self, obj: object) -> None:
        if not isinstance(obj, dict):
            return
        if obj.get("jsonrpc") != "2.0":
            return
        # Réponse JSON-RPC: result ou error
        if "result" not in obj and "error" not in obj:
            return

        resp_id = _safe_jsonrpc_id(obj.get("id"))
        if resp_id is None:
            return
        self._inflight.discard(resp_id)

    def snapshot(self) -> list[str | int | float]:
        return list(self._inflight)

    def clear(self) -> None:
        self._inflight.clear()


def _write_jsonrpc_payload(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _write_inflight_errors(
    *,
    server_name: str,
    inflight_ids: Iterable[str | int | float],
    message: str,
    max_errors: int = 100,
) -> None:
    """Émet des erreurs JSON-RPC (-32001) pour une liste d'IDs en vol.

    But: éviter un timeout IDE quand le relay ne peut pas produire la réponse.
    """

    emitted = 0
    for req_id in inflight_ids:
        if emitted >= max(1, max_errors):
            break
        payload = _jsonrpc_error(
            code=-32001,
            message=f"{server_name}: {message}",
            req_id=req_id,
        )
        try:
            _write_jsonrpc_payload(payload)
        except Exception:
            # Pas de fallback: stdout doit rester JSON only.
            return
        emitted += 1


def _try_parse_json_from_line(raw_line: bytes) -> object | None:
    stripped_left = raw_line.lstrip()
    if not stripped_left.startswith((b"{", b"[")):
        return None

    try:
        return json.loads(stripped_left.decode("utf-8", errors="replace").strip())
    except json.JSONDecodeError:
        return None


def _append_jsonl_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")


class BridgeMonitor:
    """Monitoring opt-in du trafic JSON-RPC du bridge.

    Important:
    - Ne jamais écrire sur stdout.
    - Logger uniquement de la metadata (pas de params/result).
    """

    def __init__(
        self,
        *,
        server_name: str,
        enabled: bool,
        log_path: Path | None,
        queue_max: int,
        summary_on_exit: bool,
    ) -> None:
        self._server_name = server_name
        self._enabled = enabled
        self._log_path = log_path if enabled else None
        self._queue_max = max(1, queue_max)
        self._summary_on_exit = summary_on_exit if enabled else False

        self._queue: asyncio.Queue[str | None] | None = None
        self._writer_task: asyncio.Task[None] | None = None
        self._closing = False

        self.client_to_server_requests_by_method: dict[str, int] = {}
        self.server_to_client_requests_by_method: dict[str, int] = {}
        self.responses_total: int = 0
        self.responses_error_total: int = 0

        self.log_dropped_total: int = 0
        self.log_write_errors_total: int = 0
        self.log_write_disabled: bool = False
        self.log_last_error: str | None = None

    @classmethod
    def from_env(cls, *, server_name: str) -> BridgeMonitor:
        enabled = _env_flag("MCP_BRIDGE_MONITORING_ENABLED", default=False)

        log_path_raw = os.getenv("MCP_BRIDGE_MONITORING_LOG_PATH")
        log_path = None
        if enabled and log_path_raw:
            log_path = Path(log_path_raw).expanduser().resolve(strict=False)

        queue_max = _env_int("MCP_BRIDGE_MONITORING_QUEUE_MAX", default=1000)
        summary_on_exit = _env_flag("MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT", default=enabled)

        return cls(
            server_name=server_name,
            enabled=enabled,
            log_path=log_path,
            queue_max=queue_max,
            summary_on_exit=summary_on_exit,
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def start(self) -> None:
        if not self._enabled:
            return
        if self._log_path is None:
            return
        if self._queue is not None:
            return

        self._queue = asyncio.Queue(maxsize=self._queue_max)
        self._writer_task = asyncio.create_task(self._writer_loop())

    def observe_json_line(self, *, direction: Direction, raw_line: bytes) -> None:
        if not self._enabled or self._closing:
            return

        stripped_left = raw_line.lstrip()
        if not stripped_left.startswith(b"{"):
            return

        try:
            obj = json.loads(stripped_left.decode("utf-8", errors="replace").strip())
        except json.JSONDecodeError:
            return

        self.observe_json_obj(direction=direction, obj=obj)

    def observe_json_obj(self, *, direction: Direction, obj: object) -> None:
        if not self._enabled or self._closing:
            return
        if not isinstance(obj, dict):
            return
        if obj.get("jsonrpc") != "2.0":
            return

        kind, method, req_id = self._classify_jsonrpc(obj)
        if kind is None:
            return

        if kind == "request" and method is not None:
            target = (
                self.client_to_server_requests_by_method
                if direction == "client_to_server"
                else self.server_to_client_requests_by_method
            )
            target[method] = int(target.get(method, 0)) + 1

        if kind == "response":
            self.responses_total += 1
            if "error" in obj:
                self.responses_error_total += 1

        self._enqueue_event(
            BridgeMonitorEvent(
                ts=_now_utc_iso(),
                server=self._server_name,
                direction=direction,
                kind=kind,
                method=method,
                req_id=req_id,
            )
        )

    async def stop(self) -> None:
        if not self._enabled:
            return

        self._closing = True

        queue = self._queue
        writer_task = self._writer_task
        if queue is not None and writer_task is not None:
            try:
                await asyncio.wait_for(queue.join(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

            try:
                await queue.put(None)
            except Exception:
                pass

            try:
                await asyncio.wait_for(writer_task, timeout=1.0)
            except asyncio.TimeoutError:
                writer_task.cancel()
                try:
                    await writer_task
                except asyncio.CancelledError:
                    pass

        if self._summary_on_exit:
            self.dump_summary_to_stderr()

    def dump_summary_to_stderr(self) -> None:
        try:
            sys.stderr.write(json.dumps(self.get_summary(), ensure_ascii=False) + "\n")
            sys.stderr.flush()
        except Exception:
            return

    def get_summary(self) -> dict[str, object]:
        return {
            "server": self._server_name,
            "enabled": self._enabled,
            "log_path": str(self._log_path) if self._log_path is not None else None,
            "client_to_server_requests_by_method": dict(self.client_to_server_requests_by_method),
            "server_to_client_requests_by_method": dict(self.server_to_client_requests_by_method),
            "responses_total": int(self.responses_total),
            "responses_error_total": int(self.responses_error_total),
            "log_dropped_total": int(self.log_dropped_total),
            "log_write_errors_total": int(self.log_write_errors_total),
            "log_write_disabled": bool(self.log_write_disabled),
            "log_last_error": self.log_last_error,
        }

    @staticmethod
    def _classify_jsonrpc(obj: dict[str, object]) -> tuple[EventKind | None, str | None, object | None]:
        if isinstance(obj.get("method"), str):
            return "request", str(obj.get("method")), obj.get("id")
        if "result" in obj or "error" in obj:
            return "response", None, obj.get("id")
        return None, None, obj.get("id")

    def _enqueue_event(self, event: BridgeMonitorEvent) -> None:
        if self._log_path is None:
            return
        if self._queue is None:
            return
        if self.log_write_disabled:
            return

        line = event.to_json_line()
        try:
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            self.log_dropped_total += 1

    async def _writer_loop(self) -> None:
        assert self._queue is not None

        while True:
            item = await self._queue.get()
            try:
                if item is None:
                    return

                if self._log_path is None or self.log_write_disabled:
                    continue

                try:
                    await asyncio.to_thread(_append_jsonl_line, self._log_path, item)
                except Exception as e:
                    self.log_write_errors_total += 1
                    self.log_write_disabled = True
                    self.log_last_error = str(e)
            finally:
                self._queue.task_done()


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
    # IMPORTANT: la limite par défaut (64KiB) peut faire échouer readline()
    # sur des requêtes JSON-RPC volumineuses (batch ou gros params).
    reader = asyncio.StreamReader(limit=_get_stdio_stream_limit_bytes())
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


async def _pipe_reader_to_writer_lines_with_monitor(
    *,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    monitor: BridgeMonitor,
    direction: Direction,
    inflight: InflightTracker | None = None,
) -> None:
    while True:
        line = await reader.readline()
        if not line:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            return

        monitor.observe_json_line(direction=direction, raw_line=line)

        if inflight is not None and direction == "client_to_server":
            obj = _try_parse_json_from_line(line)
            if obj is not None:
                inflight.observe_client_message(obj)

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
    server_name: str,
    monitor: BridgeMonitor | None = None,
    inflight: InflightTracker | None = None,
) -> None:
    """Relaye uniquement les lignes JSON (objets) vers stdout.

    Certains serveurs MCP stdio (ex: server-filesystem) peuvent imprimer une bannière
    ou des logs sur stdout au démarrage. Cela corrompt le flux JSON-RPC côté client.

    Stratégie:
    - si la ligne (après strip gauche) commence par '{' => forward vers stdout
    - sinon => rediriger vers stderr (best-effort)
    """

    while True:
        try:
            line = await stream.readline()
        except ValueError as e:
            # Typiquement: "Separator is not found, and chunk exceed the limit"
            # => réponse JSON-RPC trop volumineuse (ligne > limit).
            try:
                hint = (
                    "[mcp_bridge stdout relay error] "
                    + str(e)
                    + " (hint: increase MCP_BRIDGE_STDIO_STREAM_LIMIT or reduce ripgrep maxResults)\n"
                ).encode("utf-8", errors="replace")
                stderr_buffer.write(hint)
                stderr_buffer.flush()
            except Exception:
                pass

            if inflight is not None:
                _write_inflight_errors(
                    server_name=server_name,
                    inflight_ids=inflight.snapshot(),
                    message=(
                        "Réponse trop volumineuse (stdout) - "
                        + str(e)
                        + ". Augmenter MCP_BRIDGE_STDIO_STREAM_LIMIT ou réduire ripgrep maxResults."
                    ),
                )
                inflight.clear()

            # On n'élève pas l'exception: le bridge doit rester vivant et fournir
            # une erreur JSON-RPC au client plutôt qu'un timeout.
            return
        if not line:
            return

        stripped_left = line.lstrip()
        if stripped_left.startswith(b"{"):
            # Filtre minimal anti-logs JSON:
            # on ne forwarde que des objets JSON-RPC {"jsonrpc": "2.0", ...}
            try:
                candidate = json.loads(stripped_left.decode("utf-8", errors="replace"))
                if isinstance(candidate, dict) and candidate.get("jsonrpc") == "2.0":
                    if monitor is not None:
                        monitor.observe_json_obj(direction="server_to_client", obj=candidate)
                    if inflight is not None:
                        inflight.observe_server_message(candidate)
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
    monitor = BridgeMonitor.from_env(server_name="shrimp-task-manager")
    await monitor.start()

    try:
        proc = await asyncio.create_subprocess_exec(
            relay_cmd.command,
            *relay_cmd.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_get_stdio_stream_limit_bytes(),
            env=relay_cmd.env,
        )
    except Exception as e:
        # Mirror behavior from _run_stdio_relay: answer errors for every incoming request.
        while True:
            raw = await stdin_reader.readline()
            if not raw:
                await monitor.stop()
                return 1

            monitor.observe_json_line(direction="client_to_server", raw_line=raw)

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

            monitor.observe_json_obj(direction="server_to_client", obj=payload)
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    async def _pump_client_to_server() -> None:
        await _pipe_reader_to_writer_lines_with_monitor(
            reader=stdin_reader,
            writer=proc.stdin,  # type: ignore[arg-type]
            monitor=monitor,
            direction="client_to_server",
        )

    async def _pump_server_to_client_with_shim() -> None:
        try:
            while True:
                try:
                    line = await proc.stdout.readline()
                except ValueError as e:
                    try:
                        sys.stderr.write(
                            "[mcp_bridge shrimp stdout relay error] "
                            + str(e)
                            + " (hint: increase MCP_BRIDGE_STDIO_STREAM_LIMIT)\n"
                        )
                        sys.stderr.flush()
                    except Exception:
                        pass
                    raise RuntimeError("shrimp stdout line exceeded asyncio stream limit") from e
                if not line:
                    return

                stripped_left = line.lstrip()
                if stripped_left.startswith(b"{"):
                    try:
                        msg_obj = json.loads(stripped_left.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        msg_obj = None

                    if _is_jsonrpc_request_message(msg_obj) and msg_obj.get("method") == "roots/list":
                        monitor.observe_json_obj(direction="server_to_client", obj=msg_obj)
                        req_id = _extract_jsonrpc_id(msg_obj)
                        roots_payload = _build_roots_list_result(
                            req_id=req_id,
                            root_path=_get_workspace_root_for_roots_list(),
                        )
                        monitor.observe_json_obj(direction="client_to_server", obj=roots_payload)
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
                        monitor.observe_json_obj(direction="server_to_client", obj=msg_obj)
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
        {stdin_task, stdout_task, proc_wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Si stdout s'arrête avant la fin du process (EOF ou crash), on termine le process
    # pour éviter des timeouts silencieux côté client.
    if stdout_task in done and not proc_wait_task.done():
        exc = stdout_task.exception()
        try:
            if exc is None:
                sys.stderr.write("[mcp_bridge] stdout relay ended unexpectedly; terminating child\n")
            else:
                sys.stderr.write(f"[mcp_bridge] stdout relay crashed: {exc}\n")
            sys.stderr.flush()
        except Exception:
            pass
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            await proc_wait_task
        except asyncio.CancelledError:
            pass

        if not stdin_task.done():
            stdin_task.cancel()
            try:
                await stdin_task
            except asyncio.CancelledError:
                pass

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
        except Exception:
            # Ne pas faire tomber le bridge pendant la phase de drainage.
            pass

    await monitor.stop()
    return returncode


async def _run_stdio_relay(server_name: str) -> int:
    # Special-case: shrimp-task-manager uses bidirectional requests (roots/list).
    if server_name == "shrimp-task-manager":
        return await _run_shrimp_task_manager_stdio_with_roots_shim()

    relay_cmd = _build_stdio_relay_command(server_name)
    stdin_reader = await _connect_stdin_reader()
    monitor = BridgeMonitor.from_env(server_name=server_name)
    await monitor.start()
    inflight = InflightTracker()

    try:
        proc = await asyncio.create_subprocess_exec(
            relay_cmd.command,
            *relay_cmd.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_get_stdio_stream_limit_bytes(),
            env=relay_cmd.env,
        )
    except Exception as e:
        # Si le process ne démarre pas, répondre en JSON-RPC à chaque requête reçue
        # pour rendre l’erreur visible côté client.
        while True:
            raw = await stdin_reader.readline()
            if not raw:
                await monitor.stop()
                return 1

            monitor.observe_json_line(direction="client_to_server", raw_line=raw)

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

            monitor.observe_json_obj(direction="server_to_client", obj=payload)
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdin_task = asyncio.create_task(
        _pipe_reader_to_writer_lines_with_monitor(
            reader=stdin_reader,
            writer=proc.stdin,
            monitor=monitor,
            direction="client_to_server",
            inflight=inflight,
        )
    )
    stdout_task = asyncio.create_task(
        _pipe_child_stdout_jsonrpc_only(
            stream=proc.stdout,
            stdout_buffer=sys.stdout.buffer,
            stderr_buffer=sys.stderr.buffer,
            server_name=server_name,
            monitor=monitor,
            inflight=inflight,
        )
    )
    stderr_task = asyncio.create_task(
        _pipe_stream_to_buffer_lines(stream=proc.stderr, out=sys.stderr.buffer, flush=True)
    )
    proc_wait_task = asyncio.create_task(proc.wait())

    done, _pending = await asyncio.wait(
        {stdin_task, stdout_task, proc_wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Si stdout s'arrête avant la fin du process (EOF ou crash), on termine le process
    # pour éviter des timeouts silencieux côté client.
    if stdout_task in done and not proc_wait_task.done():
        exc = stdout_task.exception()

        inflight_ids = inflight.snapshot()
        if inflight_ids:
            _write_inflight_errors(
                server_name=server_name,
                inflight_ids=inflight_ids,
                message=(
                    "Le serveur MCP n'a pas pu produire une réponse (stdout interrompu). "
                    + (f"Détail: {exc}" if exc is not None else "")
                ).strip(),
            )
            inflight.clear()

        try:
            if exc is None:
                sys.stderr.write("[mcp_bridge] stdout relay ended unexpectedly; terminating child\n")
            else:
                sys.stderr.write(f"[mcp_bridge] stdout relay crashed: {exc}\n")
            sys.stderr.flush()
        except Exception:
            pass
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            await proc_wait_task
        except asyncio.CancelledError:
            pass

        if not stdin_task.done():
            stdin_task.cancel()
            try:
                await stdin_task
            except asyncio.CancelledError:
                pass

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
        except Exception:
            # Ne pas faire tomber le bridge pendant la phase de drainage.
            pass

    await monitor.stop()
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
