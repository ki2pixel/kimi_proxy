"""Tests fast-filesystem : politique de chemins et serveur HTTP.

Couvre P0 (rejet fail-closed des relatifs, racine `/` interdite, loopback/CORS)
et prépare P1 (`_meta` workspaceRoot).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = REPO_ROOT / "scripts" / "mcp_servers" / "fast_filesystem_server.py"
POLICY_PATH = REPO_ROOT / "scripts" / "mcp_servers" / "path_policy.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    if spec.name in sys.modules:
        del sys.modules[spec.name]
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_policy():
    return _load_module("test_path_policy", POLICY_PATH)


def _load_server():
    return _load_module("test_fast_filesystem_server", SERVER_PATH)


@pytest.fixture
def fs_server(tmp_path: Path):
    ffs = _load_server()
    ffs.ALLOWED_ROOT = tmp_path.resolve()
    httpd = ffs.HTTPServer(("127.0.0.1", 0), ffs.FastFilesystemHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield base_url, tmp_path, ffs
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _rpc(base_url: str, method: str, params: object, req_id: int = 1) -> httpx.Response:
    return httpx.post(
        f"{base_url}/rpc",
        json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
        timeout=5.0,
    )


def _tool(
    base_url: str,
    name: str,
    arguments: object,
    *,
    meta: dict | None = None,
    req_id: int = 1,
) -> httpx.Response:
    params: dict[str, object] = {"name": name, "arguments": arguments}
    if meta is not None:
        params["_meta"] = meta
    return _rpc(base_url, "tools/call", params, req_id=req_id)


# ---------------------------------------------------------------------------
# Politique de chemins
# ---------------------------------------------------------------------------


def test_load_allowed_root_rejects_slash(monkeypatch):
    policy = _load_policy()
    monkeypatch.setenv("MCP_ALLOWED_ROOT", "/")
    monkeypatch.delenv("MCP_ALLOWED_ROOT_UNSAFE", raising=False)
    with pytest.raises(SystemExit):
        policy.load_allowed_root()


def test_load_allowed_root_accepts_directory(monkeypatch, tmp_path):
    policy = _load_policy()
    monkeypatch.setenv("MCP_ALLOWED_ROOT", str(tmp_path))
    assert policy.load_allowed_root() == tmp_path.resolve()


def test_relative_path_without_workspace_rejected(tmp_path):
    policy = _load_policy()
    with pytest.raises(policy.RelativePathError) as exc:
        policy.resolve_allowed_path("file.txt", allowed_root=tmp_path)
    assert exc.value.reason == "RELATIVE_PATH_UNSUPPORTED"


def test_relative_path_with_workspace_resolves(tmp_path):
    policy = _load_policy()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "file.txt").write_text("ok", encoding="utf-8")
    resolved = policy.resolve_allowed_path(
        "file.txt", allowed_root=tmp_path, workspace_root=workspace
    )
    assert resolved == (workspace / "file.txt").resolve()


def test_relative_path_escape_rejected(tmp_path):
    policy = _load_policy()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    with pytest.raises(policy.RelativePathEscapesWorkspaceError):
        policy.resolve_allowed_path(
            "../outside.txt", allowed_root=tmp_path, workspace_root=workspace
        )


def test_absolute_path_outside_allowed_root_rejected(tmp_path):
    policy = _load_policy()
    with pytest.raises(policy.PathOutsideAllowedRootError):
        policy.resolve_allowed_path("/etc/hostname", allowed_root=tmp_path)


def test_workspace_root_outside_allowed_root_rejected(tmp_path):
    policy = _load_policy()
    params = {"_meta": {policy.WORKSPACE_META_KEY: "/etc"}}
    with pytest.raises(policy.WorkspaceRootError):
        policy.workspace_root_from_params(params, tmp_path)


def test_normalize_paths_is_atomic(tmp_path):
    policy = _load_policy()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("A", encoding="utf-8")
    params = {"paths": [str(workspace / "a.txt"), "b.txt"]}
    with pytest.raises(policy.RelativePathError):
        policy.normalize_path_params(params, allowed_root=tmp_path)
    assert params["paths"] == [str(workspace / "a.txt"), "b.txt"]


def test_symlink_escape_rejected(tmp_path):
    policy = _load_policy()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "link").symlink_to("/etc/hostname")
    with pytest.raises(policy.RelativePathEscapesWorkspaceError):
        policy.resolve_allowed_path(
            "link", allowed_root=tmp_path, workspace_root=workspace
        )


# ---------------------------------------------------------------------------
# Serveur HTTP — P0 fail-closed
# ---------------------------------------------------------------------------


def test_server_rejects_relative_path(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = _tool(base_url, "fast_get_directory_tree", {"path": "."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32602
    assert body["error"]["data"]["reason"] == "RELATIVE_PATH_UNSUPPORTED"


def test_server_accepts_absolute_tree(fs_server):
    base_url, tmp_path, _ffs = fs_server
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "file.txt").write_text("hello", encoding="utf-8")
    resp = _tool(
        base_url,
        "fast_get_directory_tree",
        {"path": str(workspace), "max_depth": 1, "include_files": True},
        req_id=2,
    )
    assert resp.status_code == 200
    text = resp.json()["result"]["content"][0]["text"]
    tree = json.loads(text)["tree"]
    assert tree["path"] == str(workspace)
    assert any(child.get("name") == "file.txt" for child in tree["children"])


def test_server_rejects_outside_allowed_root(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = _tool(base_url, "fast_read_file", {"path": "/etc/hostname"}, req_id=3)
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == -32000
    assert body["error"]["data"]["reason"] == "PATH_OUTSIDE_ALLOWED_ROOT"


def test_server_rejects_missing_path(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = _tool(base_url, "fast_read_file", {}, req_id=4)
    assert resp.status_code == 200
    assert resp.json()["error"]["data"]["reason"] == "PATH_REQUIRED"


def test_server_rejects_relative_write(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = _tool(
        base_url,
        "fast_write_file",
        {"path": "should-not-exist.txt", "content": "x"},
        req_id=5,
    )
    assert resp.status_code == 200
    assert resp.json()["error"]["data"]["reason"] == "RELATIVE_PATH_UNSUPPORTED"


def test_server_multiple_files_atomic(fs_server):
    base_url, tmp_path, _ffs = fs_server
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("A", encoding="utf-8")
    (workspace / "b.txt").write_text("B", encoding="utf-8")
    resp = _tool(
        base_url,
        "fast_read_multiple_files",
        {"paths": [str(workspace / "a.txt"), "b.txt"]},
        req_id=6,
    )
    assert resp.status_code == 200
    assert resp.json()["error"]["data"]["reason"] == "RELATIVE_PATH_UNSUPPORTED"


def test_server_no_cors_wildcard(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = _rpc(base_url, "tools/list", {}, req_id=7)
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_server_initialize_instructions(fs_server):
    base_url, tmp_path, _ffs = fs_server
    resp = _rpc(
        base_url,
        "initialize",
        {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {}},
        req_id=8,
    )
    assert resp.status_code == 200
    instructions = resp.json()["result"]["instructions"]
    assert "absolus" in instructions
    assert str(tmp_path) in instructions


def test_server_tool_descriptions_require_absolute_paths(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = _rpc(base_url, "tools/list", {}, req_id=9)
    tools = resp.json()["result"]["tools"]
    descriptions = " ".join(tool["description"] for tool in tools)
    assert "absolu" in descriptions
    assert "workspace-only" not in descriptions


def test_health_reports_six_tools(fs_server):
    base_url, _tmp_path, _ffs = fs_server
    resp = httpx.get(f"{base_url}/health", timeout=5.0)
    assert resp.status_code == 200
    assert resp.json()["tools_count"] == 6
    assert "access-control-allow-origin" not in resp.headers


# ---------------------------------------------------------------------------
# P1 — workspace root via _meta
# ---------------------------------------------------------------------------


def test_server_workspace_meta_resolves_relative(fs_server):
    base_url, tmp_path, ffs = fs_server
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("A", encoding="utf-8")
    meta = {ffs.WORKSPACE_META_KEY: str(workspace)}
    resp = _tool(
        base_url,
        "fast_read_file",
        {"path": "a.txt"},
        meta=meta,
        req_id=10,
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["content"][0]["text"] == "A"


def test_server_workspace_meta_escape_rejected(fs_server):
    base_url, tmp_path, ffs = fs_server
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    meta = {ffs.WORKSPACE_META_KEY: str(workspace)}
    resp = _tool(
        base_url,
        "fast_read_file",
        {"path": "../outside.txt"},
        meta=meta,
        req_id=11,
    )
    assert resp.status_code == 200
    assert resp.json()["error"]["data"]["reason"] == "RELATIVE_PATH_ESCAPES_WORKSPACE"


def test_server_invalid_workspace_meta_rejected(fs_server):
    base_url, _tmp_path, ffs = fs_server
    meta = {ffs.WORKSPACE_META_KEY: "/etc"}
    resp = _tool(
        base_url,
        "fast_read_file",
        {"path": "hostname"},
        meta=meta,
        req_id=12,
    )
    assert resp.status_code == 200
    assert resp.json()["error"]["data"]["reason"] == "INVALID_WORKSPACE_ROOT"
