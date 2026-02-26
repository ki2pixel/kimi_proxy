#!/usr/bin/env python3
"""Fake MCP stdio server for bridge verification.

Purpose:
- Provide a deterministic stdio JSON-RPC server to test the bridge behavior
  without depending on npx/network.

Behavior:
- Reads JSON-RPC messages from stdin (one per line)
- Replies with JSON-RPC 2.0 responses on stdout (one per line)

Supported methods:
- tools/list: returns a minimal tools list
- tools/call: supports two fake tools:
    - echo_small: returns a small payload
    - echo_big: returns a large string payload of requested size

Notes:
- This file is used by CLI harnesses; unit tests can import/execute it too.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _write(obj: object) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error(*, req_id: object | None, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": int(code), "message": message}}


def _tools_list(*, req_id: object | None) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "tools": [
                {
                    "name": "echo_small",
                    "description": "Retourne une petite réponse",
                    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": True},
                },
                {
                    "name": "echo_big",
                    "description": "Retourne une grande réponse (1 ligne) pour tester le bridge",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"size": {"type": "integer"}},
                        "required": ["size"],
                        "additionalProperties": True,
                    },
                },
            ]
        },
    }


def _tools_call(*, req_id: object | None, params: dict[str, Any]) -> dict[str, object]:
    name = params.get("name")
    arguments = params.get("arguments")
    if name == "echo_small":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "ok"}]}}
    if name == "echo_big":
        if not isinstance(arguments, dict) or not isinstance(arguments.get("size"), int):
            return _error(req_id=req_id, code=-32602, message="Invalid params")
        size = int(arguments["size"])
        if size < 0:
            size = 0
        payload = "x" * size
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": payload}]},
        }

    return _error(req_id=req_id, code=-32601, message="Method not found")


def main() -> int:
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _write(_error(req_id=None, code=-32700, message="Parse error"))
            continue

        if not isinstance(req, dict):
            _write(_error(req_id=None, code=-32600, message="Invalid Request"))
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params")
        if method == "tools/list":
            _write(_tools_list(req_id=req_id))
            continue
        if method == "tools/call":
            if not isinstance(params, dict):
                _write(_error(req_id=req_id, code=-32602, message="Invalid params"))
                continue
            _write(_tools_call(req_id=req_id, params=params))
            continue

        _write(_error(req_id=req_id, code=-32601, message="Method not found"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
