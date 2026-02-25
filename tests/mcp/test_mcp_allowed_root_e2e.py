"""tests.mcp.test_mcp_allowed_root_e2e

Tests E2E (serveurs réels) pour valider l'extension d'accès workspace.

Pré-requis:
    ./scripts/start-mcp-servers.sh start

Objectif:
    - Autoriser les chemins sous /home/kidpixel via MCP_ALLOWED_ROOT
    - Refuser les chemins hors /home/kidpixel (ex: /etc/passwd)
    - Bloquer les tentatives de path traversal et d'évasion via symlink
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest


def _is_fast_filesystem_available() -> bool:
    try:
        import httpx

        resp = httpx.get("http://127.0.0.1:8004/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _is_json_query_available() -> bool:
    try:
        import httpx

        resp = httpx.get("http://127.0.0.1:8005/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


async def _post_jsonrpc(url: str, payload: dict) -> "tuple[int, dict]":
    import httpx

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, json=payload)
        data = resp.json()
        return resp.status_code, data


@pytest.mark.e2e
@pytest.mark.filesystem
@pytest.mark.asyncio
@pytest.mark.skipif(not _is_fast_filesystem_available(), reason="Fast Filesystem indisponible")
async def test_fast_filesystem_allows_home_kidpixel_root() -> None:
    status, data = await _post_jsonrpc(
        "http://127.0.0.1:8004/rpc",
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "fast_list_directory",
                "arguments": {"path": "/home/kidpixel"},
            },
            "id": "allowed-1",
        },
    )

    assert status == 200
    assert "result" in data


@pytest.mark.e2e
@pytest.mark.filesystem
@pytest.mark.asyncio
@pytest.mark.skipif(not _is_fast_filesystem_available(), reason="Fast Filesystem indisponible")
async def test_fast_filesystem_blocks_outside_root() -> None:
    status, data = await _post_jsonrpc(
        "http://127.0.0.1:8004/rpc",
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "fast_read_file",
                "arguments": {"path": "/etc/passwd"},
            },
            "id": "forbidden-1",
        },
    )

    assert status == 403
    assert "error" in data


@pytest.mark.e2e
@pytest.mark.filesystem
@pytest.mark.asyncio
@pytest.mark.skipif(not _is_fast_filesystem_available(), reason="Fast Filesystem indisponible")
async def test_fast_filesystem_blocks_traversal_and_symlink_escape() -> None:
    traversal_status, traversal_data = await _post_jsonrpc(
        "http://127.0.0.1:8004/rpc",
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "fast_read_file",
                "arguments": {"path": "/home/kidpixel/../../etc/passwd"},
            },
            "id": "trav-1",
        },
    )

    assert traversal_status == 403
    assert "error" in traversal_data

    # Symlink escape
    base_dir = Path("/home/kidpixel/kimi-proxy/workspace")
    base_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="mcp_allowed_root_", dir=str(base_dir)))
    try:
        (temp_dir / "etc_link").symlink_to("/etc")

        symlink_status, symlink_data = await _post_jsonrpc(
            "http://127.0.0.1:8004/rpc",
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "fast_read_file",
                    "arguments": {"path": str(temp_dir / "etc_link" / "passwd")},
                },
                "id": "sym-1",
            },
        )

        assert symlink_status == 403
        assert "error" in symlink_data
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.e2e
@pytest.mark.json_query
@pytest.mark.asyncio
@pytest.mark.skipif(not _is_json_query_available(), reason="JSON Query indisponible")
async def test_json_query_allows_file_path_under_home_kidpixel_and_blocks_outside() -> None:
    allowed_path = "/home/kidpixel/kimi-proxy/README.md"

    allowed_status, allowed_data = await _post_jsonrpc(
        "http://127.0.0.1:8005/rpc",
        {
            "jsonrpc": "2.0",
            "method": "query_json",
            "params": {"file_path": allowed_path, "json_data": {"a": 1}, "query": "a"},
            "id": "jq-allowed",
        },
    )

    assert allowed_status == 200
    assert "result" in allowed_data

    forbidden_status, forbidden_data = await _post_jsonrpc(
        "http://127.0.0.1:8005/rpc",
        {
            "jsonrpc": "2.0",
            "method": "query_json",
            "params": {"file_path": "/etc/passwd", "json_data": {"a": 1}, "query": "a"},
            "id": "jq-forbidden",
        },
    )

    assert forbidden_status == 403
    assert "error" in forbidden_data
