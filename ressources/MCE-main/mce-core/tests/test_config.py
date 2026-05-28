"""
MCE — Config Validation Tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.mce_config import MCEConfig, TokenLimitsConfig


class TestTokenLimitsValidation:
    def test_valid_limits(self):
        cfg = TokenLimitsConfig(safe_limit=100, squeeze_trigger=200, absolute_max=500)
        assert cfg.safe_limit == 100

    def test_invalid_limits_safe_greater_than_trigger(self):
        with pytest.raises(ValueError):
            TokenLimitsConfig(safe_limit=300, squeeze_trigger=200, absolute_max=500)

    def test_invalid_limits_trigger_greater_than_max(self):
        with pytest.raises(ValueError):
            TokenLimitsConfig(safe_limit=100, squeeze_trigger=600, absolute_max=500)

    def test_equal_limits_ok(self):
        cfg = TokenLimitsConfig(safe_limit=100, squeeze_trigger=100, absolute_max=100)
        assert cfg.safe_limit == 100


class TestMCEConfigDefaults:
    def test_default_config(self):
        cfg = MCEConfig()
        assert cfg.proxy.port == 3025
        assert cfg.token_limits.safe_limit == 1000
        assert cfg.cache.enabled is True

    def test_from_yaml_missing_file(self):
        cfg = MCEConfig.from_yaml(Path("/nonexistent/config.yaml"))
        assert cfg.proxy.host == "127.0.0.1"
