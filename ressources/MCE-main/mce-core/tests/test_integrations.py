"""
MCE — Integration Tests
Verifies correct wiring and execution of PermissionGate, DriftSentinel,
and SkillForge within the reverse proxy server JSON-RPC pipeline.
"""

import sys
from pathlib import Path
import pytest
import unittest.mock as mock
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.proxy_server import ProxyServer
from schemas.mce_config import (
    MCEConfig,
    PermissionProfilesConfig,
    PermissionProfile,
    DriftSentinelConfig,
    SkillsConfig,
    TimeMachineConfig,
)
from schemas.json_rpc import JsonRpcRequest, JsonRpcResponse, JsonRpcError, ToolSchema
from engine.guardian.drift_sentinel import Constraint


@pytest.fixture
def base_config(tmp_path):
    # Set up temporary dirs
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create dummy skill
    (skills_dir / "sql.skill.md").write_text(
        """---
name: sql-safety
version: 1.0.0
triggers:
  tool_names: ["execute_sql"]
  keywords: ["SELECT"]
risk_level: high
requires_checkpoint: true
---
## Constraints
- Never select all columns without limit
## Workflow
1. Append LIMIT 10
""",
        encoding="utf-8",
    )

    return MCEConfig(
        proxy={"host": "127.0.0.1", "port": 3025},
        permission_profiles=PermissionProfilesConfig(
            active="exploration",
            profiles={
                "exploration": PermissionProfile(
                    file_read="auto", file_write="prompt", shell_exec="prompt", destructive="block"
                ),
                "focused_work": PermissionProfile(
                    file_read="auto", file_write="auto", shell_exec="prompt", destructive="prompt"
                ),
            },
        ),
        drift_sentinel=DriftSentinelConfig(
            enabled=True,
            alert_on_constraint_violation=True,
            block_on_critical_violation=True,
            load_constraints_from_memvault=False,
        ),
        skills=SkillsConfig(
            enabled=True,
            path=str(skills_dir),
            auto_trigger=True,
        ),
        time_machine=TimeMachineConfig(
            enabled=True,
        ),
        memvault={"enabled": False},
        cost_watch={"enabled": False},
    )


@pytest.mark.asyncio
class TestIntegrations:
    async def test_permission_gate_block(self, base_config):
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()
        # Mock mcp client
        proxy.mcp_client.call_tool = mock.AsyncMock()

        # Exploration profile blocks "destructive" tools like "delete_file"
        req = JsonRpcRequest(id=1, method="delete_file", params={"path": "main.py"})
        response = await proxy._process_request(req)

        assert response.error is not None
        assert response.error.code == -32001
        assert "Blocked by 'exploration' profile" in response.error.message
        proxy.mcp_client.call_tool.assert_not_called()

    async def test_permission_gate_auto_allow(self, base_config):
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()
        # Mock mcp client to return success
        proxy.mcp_client.call_tool = mock.AsyncMock(
            return_value=JsonRpcResponse(id=1, result="file contents here")
        )

        # Exploration profile auto-allows "read_file" without prompting PolicyEngine
        req = JsonRpcRequest(id=1, method="read_file", params={"path": "main.py"})
        response = await proxy._process_request(req)

        assert response.error is None
        assert response.result == "file contents here"
        proxy.mcp_client.call_tool.assert_called_once()

    async def test_drift_sentinel_critical_violation_block(self, base_config):
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()

        # Add a critical constraint to drift sentinel
        proxy._drift_sentinel.add_constraint(
            Constraint(
                id="c_critical",
                description="Do not leak credential details",
                pattern="password|secret_key",
                severity="CRITICAL",
            )
        )

        # Mock mcp client to return a payload containing violating secret_key
        proxy.mcp_client.call_tool = mock.AsyncMock(
            return_value=JsonRpcResponse(id=1, result={"config": "secret_key = 12345"})
        )

        req = JsonRpcRequest(id=1, method="read_file", params={"path": "config.txt"})
        response = await proxy._process_request(req)

        # The response should be blocked due to the critical drift sentinel violation
        assert response.error is not None
        assert response.error.code == -32001
        assert "violate constraint: Do not leak credential" in response.error.message

    async def test_skill_forge_checkpoint_and_notices(self, base_config):
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()

        # Mock mcp client
        proxy.mcp_client.call_tool = mock.AsyncMock(
            return_value=JsonRpcResponse(id=1, result="SQL Query Run Successfully")
        )

        # Mock TimeMachine checkpoint
        proxy._time_machine.checkpoint = mock.AsyncMock(
            return_value=mock.MagicMock(sequence=1, id="cp123", label="mock cp")
        )

        # Triggers "sql-safety" skill on method "execute_sql"
        req = JsonRpcRequest(id=1, method="execute_sql", params={"query": "SELECT * FROM users;"})
        response = await proxy._process_request(req)

        # Should trigger a checkpoint since requires_checkpoint is True
        proxy._time_machine.checkpoint.assert_called_once()

        # Notices (constraints/workflows) should be appended
        assert response.result is not None
        assert "[MCE Skill: sql-safety v1.0.0]" in response.result
        assert "Never select all columns without limit" in response.result
        assert "Append LIMIT 10" in response.result

    async def test_circuit_breaker_logical_errors(self, base_config):
        base_config.circuit_breaker.failure_threshold = 3
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()

        # Mock mcp client to return a logical tool error result (isError: True)
        proxy.mcp_client.call_tool = mock.AsyncMock(
            return_value=JsonRpcResponse(id=1, result={"isError": True})
        )

        req = JsonRpcRequest(id=1, method="execute_command", params={"command": "npm run build"})

        # Run 1 & 2: logical error recorded, breaker doesn't trip yet
        res1 = await proxy._process_request(req)
        assert res1.result == {"isError": True}

        res2 = await proxy._process_request(req)
        assert res2.result == {"isError": True}

        # Run 3: trips the circuit breaker
        res3 = await proxy._process_request(req)
        assert res3.error is not None
        assert res3.error.code == -32002
        assert "stuck in a loop" in res3.error.message

    async def test_cache_invalidation_on_mutation(self, base_config):
        base_config.cache.enabled = True
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()

        # Mock client for reading file
        proxy.mcp_client.call_tool = mock.AsyncMock()

        req_read = JsonRpcRequest(id=1, method="read_file", params={"path": "main.py"})
        req_write = JsonRpcRequest(id=2, method="write_file", params={"path": "main.py", "content": "changed"})

        # 1. First read returns content_1
        proxy.mcp_client.call_tool.return_value = JsonRpcResponse(id=1, result="content_1")
        res1 = await proxy._process_request(req_read)
        assert res1.result == "content_1"

        # 2. Second read uses cache (even if upstream has changed to content_2)
        proxy.mcp_client.call_tool.return_value = JsonRpcResponse(id=1, result="content_2")
        res2 = await proxy._process_request(req_read)
        assert res2.result == "content_1"  # cached!

        # 3. Call mutating tool write_file
        proxy.mcp_client.call_tool.return_value = JsonRpcResponse(id=2, result="success")
        await proxy._process_request(req_write)

        # 4. Third read should now bypass cache (cache miss) and return content_2
        proxy.mcp_client.call_tool.return_value = JsonRpcResponse(id=1, result="content_2")
        res3 = await proxy._process_request(req_read)
        assert res3.result == "content_2"  # cache cleared and refetched!

    async def test_release_capabilities_meta_tool(self, base_config):
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()

        # Pre-register a tool
        schema = ToolSchema(name="read_file", description="read", domain="filesystem")
        proxy.registrar.register_tool(schema)

        # 1. Discover capability (loads domain)
        req_discover = JsonRpcRequest(id=1, method="discover_capabilities", params={"domain": "filesystem"})
        await proxy._process_request(req_discover)
        assert "read_file" in proxy.registrar.active_tool_names

        # 2. Release capability (unloads domain)
        req_release = JsonRpcRequest(id=2, method="release_capabilities", params={"domain": "filesystem"})
        res = await proxy._process_request(req_release)
        assert res.result == {"status": "success", "message": "Released domain @filesystem"}
        assert "read_file" not in proxy.registrar.active_tool_names

    async def test_search_tools_meta_tool(self, base_config):
        proxy = ProxyServer(base_config)
        await proxy._init_intelligence()

        # Register tools
        proxy.registrar.register_tool(ToolSchema(name="grep_search", description="search text inside files", domain="filesystem"))
        proxy.registrar.register_tool(ToolSchema(name="execute_sql", description="execute queries on relational DB", domain="database"))

        # Verify not active initially
        assert "grep_search" not in proxy.registrar.active_tool_names
        assert "execute_sql" not in proxy.registrar.active_tool_names

        # Call search_tools for filesystem search with top_k=1
        req = JsonRpcRequest(id=1, method="search_tools", params={"query": "find matching text patterns in local files", "top_k": 1})
        res = await proxy._process_request(req)

        # Should match and dynamically activate grep_search
        assert len(res.result) > 0
        assert res.result[0]["name"] == "grep_search"
        assert "grep_search" in proxy.registrar.active_tool_names
        assert "execute_sql" not in proxy.registrar.active_tool_names


class TestHttpEndpoints:
    def test_http_profile_switch_endpoint(self, base_config):
        proxy = ProxyServer(base_config)
        # Create a test client using context manager to trigger lifespan events
        with TestClient(proxy.app) as client:
            # Query stats/health first to verify active profile
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["stats"]["guardian"]["active_profile"] == "exploration"

            # Switch profile via endpoint
            response = client.post("/profile/switch", json={"profile": "focused_work"})
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            assert response.json()["profile"] == "focused_work"

            # Query health again to verify it has updated in memory
            response = client.get("/health")
            data = response.json()
            assert data["stats"]["guardian"]["active_profile"] == "focused_work"
