"""
Tests MCP - Suite de tests pour la refactorisation modulaire.

Structure:
- test_mcp_qdrant.py: Tests Qdrant (recherche, clustering)
- test_mcp_compression.py: Tests compression (zlib, context_aware)
- test_mcp_task_master.py: Tests Task Master (14 outils)
- test_mcp_sequential.py: Tests Sequential Thinking
- test_mcp_filesystem.py: Tests Fast Filesystem (25 outils)
- test_mcp_json_query.py: Tests JSON Query
- test_mcp_client_integration.py: Tests facade et singleton
- test_mcp_e2e.py: Tests E2E avec vrais serveurs

Fixtures:
- mock_rpc_client: Mock du RPC client
- mock_config: Config de test
- mcp_client: Client MCP avec fixtures
"""

import pytest
pytest.register_assert_rewrite("tests.mcp.test_mcp_qdrant")
pytest.register_assert_rewrite("tests.mcp.test_mcp_compression")
pytest.register_assert_rewrite("tests.mcp.test_mcp_task_master")
pytest.register_assert_rewrite("tests.mcp.test_mcp_sequential")
pytest.register_assert_rewrite("tests.mcp.test_mcp_filesystem")
pytest.register_assert_rewrite("tests.mcp.test_mcp_json_query")
pytest.register_assert_rewrite("tests.mcp.test_mcp_client_integration")
