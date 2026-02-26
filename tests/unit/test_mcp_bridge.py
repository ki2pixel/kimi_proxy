"""Tests unitaires — scripts/mcp_bridge.py.

Objectifs:
    - Vérifier la sélection des modes (gateway-http vs stdio-relay)
    - Vérifier la construction des commandes relay (env/args)
    - Vérifier le filtrage stdout JSON-RPC (bannières/logs -> stderr)
    - Vérifier les erreurs JSON-RPC retournées dans les cas invalides

Contraintes:
    - Aucun appel réseau externe
    - Pas d'exécution réelle de npx/shrimp-task-manager (mock uniquement)
"""

from __future__ import annotations

import asyncio
import json
import io
from pathlib import Path

import pytest


def _import_mcp_bridge():
    """Import local du script (évite les imports au niveau module pour tests)."""
    import importlib.util
    import sys
    from pathlib import Path

    bridge_path = Path(__file__).resolve().parents[2] / "scripts" / "mcp_bridge.py"
    # IMPORTANT: le module doit être présent dans sys.modules AVANT exec_module,
    # sinon dataclasses peut échouer (référence sys.modules[__module__]).
    spec = importlib.util.spec_from_file_location("scripts.mcp_bridge", bridge_path)
    assert spec is not None
    assert spec.loader is not None

    # Re-import isolé par test (évite pollution globale inter-tests)
    if spec.name in sys.modules:
        del sys.modules[spec.name]

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_get_gateway_url_uses_env_default_and_formats_correctly(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.delenv("MCP_GATEWAY_BASE_URL", raising=False)
    assert (
        mcp_bridge._get_gateway_url("sequential-thinking")
        == "http://localhost:8000/api/mcp-gateway/sequential-thinking/rpc"
    )

    monkeypatch.setenv("MCP_GATEWAY_BASE_URL", "http://127.0.0.1:9999/")
    assert (
        mcp_bridge._get_gateway_url("json-query")
        == "http://127.0.0.1:9999/api/mcp-gateway/json-query/rpc"
    )


@pytest.mark.unit
def test_base_relay_env_respects_bridge_path_env(monkeypatch):
    mcp_bridge = _import_mcp_bridge()

    monkeypatch.setenv("PATH", "/do/not/use")
    monkeypatch.setenv("MCP_BRIDGE_PATH_ENV", "/usr/bin:/bin")

    env = mcp_bridge._base_relay_env()
    assert env["PATH"] == "/usr/bin:/bin"


@pytest.mark.unit
def test_build_filesystem_agent_command_includes_allowed_root(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.setenv("MCP_FILESYSTEM_ALLOWED_ROOT", "/tmp")
    monkeypatch.setenv("MCP_FILESYSTEM_COMMAND", "npx")
    monkeypatch.delenv("MCP_BRIDGE_PATH_ENV", raising=False)

    cmd = mcp_bridge._build_filesystem_agent_command()
    assert cmd.command == "npx"
    assert cmd.args[-1] == "/tmp"
    assert "@modelcontextprotocol/server-filesystem" in cmd.args


@pytest.mark.unit
def test_build_ripgrep_agent_command_includes_mcp_ripgrep(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.setenv("MCP_RIPGREP_COMMAND", "npx")
    monkeypatch.delenv("MCP_BRIDGE_PATH_ENV", raising=False)

    cmd = mcp_bridge._build_ripgrep_agent_command()
    assert cmd.command == "npx"
    assert "mcp-ripgrep" in cmd.args


@pytest.mark.unit
def test_build_shrimp_task_manager_command_uses_env_or_default(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.delenv("MCP_SHRIMP_TASK_MANAGER_COMMAND", raising=False)

    cmd = mcp_bridge._build_shrimp_task_manager_command()
    # Should use default path if exists, else "shrimp-task-manager"
    expected_cmd = "/home/kidpixel/.local/bin/shrimp-task-manager" if Path("/home/kidpixel/.local/bin/shrimp-task-manager").exists() else "shrimp-task-manager"
    assert cmd.command == expected_cmd
    assert cmd.args == []


@pytest.mark.unit
def test_build_shrimp_task_manager_command_respects_env(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.setenv("MCP_SHRIMP_TASK_MANAGER_COMMAND", "/custom/path/shrimp")

    cmd = mcp_bridge._build_shrimp_task_manager_command()
    assert cmd.command == "/custom/path/shrimp"
    assert cmd.args == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_pipe_child_stdout_jsonrpc_only_filters_non_jsonrpc_to_stderr():
    mcp_bridge = _import_mcp_bridge()

    # Stream fake (duck-typing) pour éviter de dépendre d'impl détails de StreamReader.
    class _FakeStream:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines

        async def readline(self) -> bytes:
            return self._lines.pop(0) if self._lines else b""

    stdout_buf = bytearray()
    stderr_buf = bytearray()

    class _Buf:
        def __init__(self, target: bytearray) -> None:
            self._t = target

        def write(self, b: bytes) -> None:
            self._t.extend(b)

        def flush(self) -> None:
            return

    msg = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    stream = _FakeStream(
        [
            b"Secure MCP Filesystem Server running on stdio\n",
            b"{\"hello\": \"world\"}\n",
            (json.dumps(msg) + "\n").encode("utf-8"),
        ]
    )

    await mcp_bridge._pipe_child_stdout_jsonrpc_only(
        stream=stream,
        stdout_buffer=_Buf(stdout_buf),
        stderr_buffer=_Buf(stderr_buf),
        server_name="filesystem-agent",
    )

    stdout_text = stdout_buf.decode("utf-8", errors="replace")
    stderr_text = stderr_buf.decode("utf-8", errors="replace")

    # Seul le message JSON-RPC doit se retrouver sur stdout
    assert "\"jsonrpc\": \"2.0\"" in stdout_text
    assert "Secure MCP Filesystem Server" not in stdout_text
    assert "hello" not in stdout_text

    # Les autres lignes sont redirigées vers stderr
    assert "Secure MCP Filesystem Server" in stderr_text


@pytest.mark.asyncio
@pytest.mark.unit
async def test_pipe_child_stdout_jsonrpc_only_emits_jsonrpc_error_on_readline_limit_overrun(monkeypatch):
    mcp_bridge = _import_mcp_bridge()

    class _FakeStream:
        async def readline(self) -> bytes:
            raise ValueError("Separator is not found, and chunk exceed the limit")

    stdout_buf = bytearray()
    stderr_buf = bytearray()

    class _Buf:
        def __init__(self, target: bytearray) -> None:
            self._t = target

        def write(self, b: bytes) -> None:
            self._t.extend(b)

        def flush(self) -> None:
            return

    # Capture stdout JSON-RPC error payload
    out = io.StringIO()
    monkeypatch.setattr(mcp_bridge.sys, "stdout", out)

    inflight = mcp_bridge.InflightTracker()
    inflight.observe_client_message({"jsonrpc": "2.0", "id": 123, "method": "tools/call", "params": {}})

    await mcp_bridge._pipe_child_stdout_jsonrpc_only(
        stream=_FakeStream(),
        stdout_buffer=_Buf(stdout_buf),
        stderr_buffer=_Buf(stderr_buf),
        server_name="ripgrep-agent",
        inflight=inflight,
    )

    stderr_text = stderr_buf.decode("utf-8", errors="replace")
    assert "MCP_BRIDGE_STDIO_STREAM_LIMIT" in stderr_text
    assert "chunk exceed the limit" in stderr_text

    payload = json.loads(out.getvalue().splitlines()[0])
    assert payload["error"]["code"] == -32001
    assert payload["id"] == 123


@pytest.mark.unit
def test_get_stdio_stream_limit_bytes_clamps_env(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.setenv("MCP_BRIDGE_STDIO_STREAM_LIMIT", "1")
    assert mcp_bridge._get_stdio_stream_limit_bytes() >= 64 * 1024
    monkeypatch.setenv("MCP_BRIDGE_STDIO_STREAM_LIMIT", str(999999999))
    assert mcp_bridge._get_stdio_stream_limit_bytes() <= 64 * 1024 * 1024


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_gateway_http_parse_error_returns_jsonrpc_error(monkeypatch):
    mcp_bridge = _import_mcp_bridge()

    # Mock stdin reader
    class _FakeReader:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines

        async def readline(self) -> bytes:
            return self._lines.pop(0) if self._lines else b""

    async def _fake_connect_stdin_reader():
        return _FakeReader([b"not-json\n", b""])

    monkeypatch.setattr(mcp_bridge, "_connect_stdin_reader", _fake_connect_stdin_reader)

    # Capture stdout
    out = io.StringIO()
    monkeypatch.setattr(mcp_bridge.sys, "stdout", out)

    # Mock httpx client used by _run_gateway_http: it should never be called here
    class _DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_a, **_kw):
            raise AssertionError("httpx post should not be called for parse error")

    monkeypatch.setattr(mcp_bridge.httpx, "AsyncClient", lambda *a, **kw: _DummyClient())

    await mcp_bridge._run_gateway_http("json-query")

    payload = json.loads(out.getvalue().splitlines()[0])
    assert payload["error"]["code"] == -32700


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_gateway_http_forwards_to_expected_url(monkeypatch):
    mcp_bridge = _import_mcp_bridge()

    request_obj = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    response_obj = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}

    class _FakeReader:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines

        async def readline(self) -> bytes:
            return self._lines.pop(0) if self._lines else b""

    async def _fake_connect_stdin_reader():
        return _FakeReader([json.dumps(request_obj).encode("utf-8") + b"\n", b""])

    monkeypatch.setattr(mcp_bridge, "_connect_stdin_reader", _fake_connect_stdin_reader)

    captured: dict[str, object] = {}

    class _DummyResponse:
        def json(self) -> object:
            return response_obj

    class _DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: object):
            captured["url"] = url
            captured["json"] = json
            return _DummyResponse()

    monkeypatch.setattr(mcp_bridge.httpx, "AsyncClient", lambda *a, **kw: _DummyClient())

    out = io.StringIO()
    monkeypatch.setattr(mcp_bridge.sys, "stdout", out)

    monkeypatch.setenv("MCP_GATEWAY_BASE_URL", "http://localhost:8000")
    await mcp_bridge._run_gateway_http("json-query")

    assert captured["url"] == "http://localhost:8000/api/mcp-gateway/json-query/rpc"
    assert captured["json"] == request_obj

    line = out.getvalue().splitlines()[0]
    assert json.loads(line) == response_obj


@pytest.mark.asyncio
@pytest.mark.unit
async def test_run_stdio_relay_returns_jsonrpc_error_when_subprocess_fails(monkeypatch):
    mcp_bridge = _import_mcp_bridge()

    class _FakeReader:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines

        async def readline(self) -> bytes:
            return self._lines.pop(0) if self._lines else b""

    async def _fake_connect_stdin_reader():
        req = {"jsonrpc": "2.0", "id": 99, "method": "initialize", "params": {}}
        return _FakeReader([json.dumps(req).encode("utf-8") + b"\n", b""])

    monkeypatch.setattr(mcp_bridge, "_connect_stdin_reader", _fake_connect_stdin_reader)

    async def _raise(*_a, **_kw):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _raise)

    out = io.StringIO()
    monkeypatch.setattr(mcp_bridge.sys, "stdout", out)

    await mcp_bridge._run_stdio_relay("ripgrep-agent")
    payload = json.loads(out.getvalue().splitlines()[0])
    assert payload["error"]["code"] == -32603
    assert payload["id"] == 99


@pytest.mark.asyncio
@pytest.mark.unit
async def test_main_routes_by_server_name(monkeypatch):
    mcp_bridge = _import_mcp_bridge()

    called: list[str] = []

    async def _fake_gateway(server_name: str) -> int:
        called.append(f"gateway:{server_name}")
        return 0

    async def _fake_relay(server_name: str) -> int:
        called.append(f"relay:{server_name}")
        return 0

    monkeypatch.setattr(mcp_bridge, "_run_gateway_http", _fake_gateway)
    monkeypatch.setattr(mcp_bridge, "_run_stdio_relay", _fake_relay)

    # gateway
    monkeypatch.setattr(mcp_bridge.sys, "argv", ["mcp_bridge.py", "json-query"])
    await mcp_bridge.main()

    # relay
    monkeypatch.setattr(mcp_bridge.sys, "argv", ["mcp_bridge.py", "filesystem-agent"])
    await mcp_bridge.main()

    assert called == ["gateway:json-query", "relay:filesystem-agent"]


@pytest.mark.unit
def test_bridge_monitor_from_env_disabled_by_default(monkeypatch):
    mcp_bridge = _import_mcp_bridge()
    monkeypatch.delenv("MCP_BRIDGE_MONITORING_ENABLED", raising=False)
    monkeypatch.delenv("MCP_BRIDGE_MONITORING_LOG_PATH", raising=False)
    monkeypatch.delenv("MCP_BRIDGE_MONITORING_QUEUE_MAX", raising=False)
    monkeypatch.delenv("MCP_BRIDGE_MONITORING_SUMMARY_ON_EXIT", raising=False)

    monitor = mcp_bridge.BridgeMonitor.from_env(server_name="filesystem-agent")
    assert monitor.enabled is False


@pytest.mark.unit
def test_bridge_monitor_counts_requests_and_responses():
    mcp_bridge = _import_mcp_bridge()

    monitor = mcp_bridge.BridgeMonitor(
        server_name="filesystem-agent",
        enabled=True,
        log_path=None,
        queue_max=10,
        summary_on_exit=False,
    )

    req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"secret": "x"}}
    monitor.observe_json_obj(direction="client_to_server", obj=req)
    assert monitor.client_to_server_requests_by_method["tools/call"] == 1

    resp_ok = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    monitor.observe_json_obj(direction="server_to_client", obj=resp_ok)
    assert monitor.responses_total == 1
    assert monitor.responses_error_total == 0

    resp_err = {"jsonrpc": "2.0", "id": 2, "error": {"code": -1, "message": "boom"}}
    monitor.observe_json_obj(direction="server_to_client", obj=resp_err)
    assert monitor.responses_total == 2
    assert monitor.responses_error_total == 1

    # Non-JSON-RPC => ignoré
    monitor.observe_json_obj(direction="client_to_server", obj={"hello": "world"})
    assert monitor.client_to_server_requests_by_method["tools/call"] == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bridge_monitor_writes_jsonl_without_params_or_result(tmp_path):
    mcp_bridge = _import_mcp_bridge()

    log_path = tmp_path / "mcp_bridge.jsonl"
    monitor = mcp_bridge.BridgeMonitor(
        server_name="filesystem-agent",
        enabled=True,
        log_path=log_path,
        queue_max=50,
        summary_on_exit=False,
    )
    await monitor.start()

    req = {"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {"secret": "x"}}
    resp = {"jsonrpc": "2.0", "id": 10, "result": {"tools": []}}
    monitor.observe_json_obj(direction="client_to_server", obj=req)
    monitor.observe_json_obj(direction="server_to_client", obj=resp)

    await monitor.stop()

    text = log_path.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) >= 2

    parsed = [json.loads(ln) for ln in lines]
    for obj in parsed:
        # Ne jamais logguer de payloads potentiellement sensibles.
        assert "params" not in obj
        assert "result" not in obj
        assert "error" not in obj

    assert any(o.get("kind") == "request" and o.get("method") == "tools/list" for o in parsed)
    assert any(o.get("kind") == "response" for o in parsed)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bridge_monitor_queue_overflow_increments_drops(monkeypatch, tmp_path):
    mcp_bridge = _import_mcp_bridge()

    async def _slow_to_thread(func, /, *args, **kwargs):
        # Ralentit artificiellement le writer pour déclencher la backpressure.
        await asyncio.sleep(0.05)
        return func(*args, **kwargs)

    monkeypatch.setattr(mcp_bridge.asyncio, "to_thread", _slow_to_thread)

    log_path = tmp_path / "mcp_bridge_overflow.jsonl"
    monitor = mcp_bridge.BridgeMonitor(
        server_name="ripgrep-agent",
        enabled=True,
        log_path=log_path,
        queue_max=1,
        summary_on_exit=False,
    )
    await monitor.start()

    for i in range(100):
        req = {"jsonrpc": "2.0", "id": i, "method": "tools/list", "params": {"n": i}}
        monitor.observe_json_obj(direction="client_to_server", obj=req)

    await monitor.stop()
    assert monitor.log_dropped_total > 0

