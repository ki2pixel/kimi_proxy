from __future__ import annotations

import json

import pytest

from kimi_proxy.config.loader import MCPToolPruningConfig, MCPToolPruningOptionsConfig
from kimi_proxy.features.mcp_tool_pruning import (
    MCPToolPruningMetricsCollector,
    maybe_prune_jsonrpc_response,
    resolve_mcp_tool_pruning_config,
)


def _build_cfg(*, min_chars: int = 1, excluded_dirs: tuple[str, ...] | None = None):
    return resolve_mcp_tool_pruning_config(
        MCPToolPruningConfig(
            enabled=True,
            min_chars=min_chars,
            timeout_ms=1500,
            max_chars_fallback=0,
            excluded_dirs=excluded_dirs or (".agents", ".cline", ".clinerules", ".windsurf"),
            options=MCPToolPruningOptionsConfig(
                max_prune_ratio=0.55,
                min_keep_lines=1,
                timeout_ms=1500,
                annotate_lines=True,
                include_markers=True,
            ),
        )
    )


@pytest.mark.asyncio
async def test_maybe_prune_skips_when_request_path_is_in_excluded_dir():
    metrics = MCPToolPruningMetricsCollector()
    cfg = _build_cfg(min_chars=1)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/repo/.clinerules/rules.md"}},
    }
    response = {"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "X" * 100}]}}

    async def _pruner(**kwargs):
        raise AssertionError("pruner must not be called for excluded paths")

    out = await maybe_prune_jsonrpc_response(
        server_name="fast-filesystem",
        request_json=request,
        response_json=response,
        cfg=cfg,
        pruner=_pruner,
        metrics=metrics,
    )

    snapshot = await metrics.snapshot()
    assert out == response
    assert snapshot.skipped_excluded_path == 1
    assert snapshot.eligible_total == 0


@pytest.mark.asyncio
async def test_maybe_prune_keeps_normal_flow_when_path_not_excluded():
    cfg = _build_cfg(min_chars=1)
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/repo/src/app.py"}},
    }
    response = {"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "ORIGINAL"}]}}

    async def _pruner(**kwargs):
        return {"pruned_text": "PRUNED"}

    out = await maybe_prune_jsonrpc_response(
        server_name="fast-filesystem",
        request_json=request,
        response_json=response,
        cfg=cfg,
        pruner=_pruner,
    )

    assert out["result"]["content"][0]["text"] == "PRUNED"


@pytest.mark.asyncio
async def test_maybe_prune_detects_path_traversal_into_excluded_dir():
    cfg = _build_cfg(min_chars=1)
    request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"directory": "../.cline/cache/state.json"}},
    }
    response = {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "ORIGINAL"}]}}

    async def _pruner(**kwargs):
        raise AssertionError("pruner must not be called for excluded traversal path")

    out = await maybe_prune_jsonrpc_response(
        server_name="fast-filesystem",
        request_json=request,
        response_json=response,
        cfg=cfg,
        pruner=_pruner,
    )

    assert out == response


@pytest.mark.asyncio
async def test_maybe_prune_detects_windows_separator_excluded_dir():
    cfg = _build_cfg(min_chars=1)
    request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": r"C:\repo\.windsurf\state.json"}},
    }
    response = {"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": "ORIGINAL"}]}}

    async def _pruner(**kwargs):
        raise AssertionError("pruner must not be called for excluded windows path")

    out = await maybe_prune_jsonrpc_response(
        server_name="filesystem-agent",
        request_json=request,
        response_json=response,
        cfg=cfg,
        pruner=_pruner,
    )

    assert out == response


@pytest.mark.asyncio
async def test_maybe_prune_skips_when_response_json_contains_excluded_path():
    cfg = _build_cfg(min_chars=1)
    request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": "search_files", "arguments": {"path": "/repo/src"}},
    }
    response_payload = {
        "items": [
            {"path": "/repo/src/app.py"},
            {"path": "/repo/.agents/tasks.yml"},
        ]
    }
    response = {
        "jsonrpc": "2.0",
        "id": 5,
        "result": {"content": [{"type": "text", "text": json.dumps(response_payload)}]},
    }

    async def _pruner(**kwargs):
        raise AssertionError("pruner must not be called when response JSON contains excluded path")

    out = await maybe_prune_jsonrpc_response(
        server_name="fast-filesystem",
        request_json=request,
        response_json=response,
        cfg=cfg,
        pruner=_pruner,
    )

    assert out == response


@pytest.mark.asyncio
async def test_maybe_prune_keeps_fail_open_on_malformed_json_text():
    cfg = _build_cfg(min_chars=1)
    request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {"name": "read_text_file", "arguments": {"path": "/repo/src/app.py"}},
    }
    response = {
        "jsonrpc": "2.0",
        "id": 6,
        "result": {"content": [{"type": "text", "text": '{"path": "/repo/.cline/file"'}]},
    }

    calls = {"count": 0}

    async def _pruner(**kwargs):
        calls["count"] += 1
        return {"pruned_text": "SAFE_PRUNED"}

    out = await maybe_prune_jsonrpc_response(
        server_name="fast-filesystem",
        request_json=request,
        response_json=response,
        cfg=cfg,
        pruner=_pruner,
    )

    assert calls["count"] == 1
    assert out["result"]["content"][0]["text"] == "SAFE_PRUNED"


def test_resolve_mcp_tool_pruning_config_prefers_env_for_excluded_dirs(monkeypatch):
    monkeypatch.setenv("KIMI_MCP_TOOL_PRUNING_EXCLUDED_DIRS", " .agents, .windsurf , .agents ")

    cfg = resolve_mcp_tool_pruning_config(
        MCPToolPruningConfig(
            enabled=True,
            excluded_dirs=(".clinerules",),
        )
    )

    assert cfg.excluded_dirs == frozenset({".agents", ".windsurf"})