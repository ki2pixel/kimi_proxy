#!/usr/bin/env python3
"""Harness: verify scripts/mcp_bridge.py behavior under nominal + oversized stdout.

This script starts the bridge in stdio relay mode but replaces the child command
(`npx mcp-ripgrep`) with a local fake MCP stdio server.

Goals:
- Nominal: small JSON-RPC request/response works
- Failure mode: when response exceeds the stream limit, bridge emits JSON-RPC -32001
  for inflight IDs (no hang / no silent timeout)

Usage:
    python3 tests/mcp/harness_bridge_stdio_limits.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _send(proc: subprocess.Popen[bytes], msg: dict[str, object]) -> None:
    proc.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()


def _recv_line(proc: subprocess.Popen[bytes]) -> dict[str, object]:
    raw = proc.stdout.readline()
    if not raw:
        raise RuntimeError("EOF from bridge")
    return json.loads(raw.decode("utf-8", errors="replace"))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    bridge = repo_root / "scripts" / "mcp_bridge.py"
    fake_server = repo_root / "tests" / "fixtures" / "fake_mcp_server_stdio.py"

    tmp_dir = Path("/tmp/kimi-proxy")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Create a wrapper to replace `npx` so the bridge uses our fake server.
    wrapper_dir = tmp_dir / "bridge-harness-bin"
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    npx_wrapper = wrapper_dir / "npx"
    npx_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"exec python3 {str(fake_server)}\n",
        encoding="utf-8",
    )
    npx_wrapper.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{wrapper_dir}:{env.get('PATH','')}"
    env["MCP_RIPGREP_COMMAND"] = "npx"
    # Force a small stream limit so we can trigger the overrun deterministically.
    env["MCP_BRIDGE_STDIO_STREAM_LIMIT"] = str(64 * 1024)

    proc = subprocess.Popen(
        ["python3", str(bridge), "ripgrep-agent"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    # Nominal: tools/list
    _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    resp1 = _recv_line(proc)
    if resp1.get("id") != 1 or "result" not in resp1:
        raise RuntimeError(f"Unexpected response: {resp1}")

    # Oversized response: request a payload that should exceed the 64KiB limit.
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo_big", "arguments": {"size": 200_000}},
        },
    )
    resp2 = _recv_line(proc)
    if resp2.get("id") != 2:
        raise RuntimeError(f"Unexpected id: {resp2}")
    if "error" not in resp2 or resp2["error"].get("code") != -32001:
        raise RuntimeError(f"Expected -32001 error, got: {resp2}")

    proc.terminate()
    try:
        proc.wait(timeout=2)
    except Exception:
        proc.kill()

    # Also assert we wrote something meaningful on stderr (diagnostic hint).
    stderr_text = proc.stderr.read().decode("utf-8", errors="replace")
    if "chunk exceed the limit" not in stderr_text and "stdout relay error" not in stderr_text:
        raise RuntimeError("Expected stderr hint about stdout relay error")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
