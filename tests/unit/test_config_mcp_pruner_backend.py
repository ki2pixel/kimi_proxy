from __future__ import annotations

from typing import Dict, Any

import pytest

from kimi_proxy.config.loader import MCPPrunerBackendConfig, get_mcp_pruner_backend_config


def test_get_mcp_pruner_backend_config_defaults_when_absent() -> None:
    cfg = get_mcp_pruner_backend_config({})
    assert cfg == MCPPrunerBackendConfig()


def test_get_mcp_pruner_backend_config_parses_and_clamps() -> None:
    config: Dict[str, Any] = {
        "mcp_pruner": {
            "backend": "deepinfra",
            "deepinfra_timeout_ms": -5,
            "deepinfra_max_docs": 999999,
            "cache_ttl_s": 0,
            "cache_max_entries": 0,
        }
    }
    cfg = get_mcp_pruner_backend_config(config)
    assert cfg.backend == "deepinfra"
    assert cfg.deepinfra_timeout_ms == 1
    assert cfg.deepinfra_max_docs == 512
    assert cfg.cache_ttl_s == 1
    assert cfg.cache_max_entries == 1


def test_get_mcp_pruner_backend_config_unknown_backend_falls_back_to_heuristic() -> None:
    cfg = get_mcp_pruner_backend_config({"mcp_pruner": {"backend": "???"}})
    assert cfg.backend == "heuristic"
