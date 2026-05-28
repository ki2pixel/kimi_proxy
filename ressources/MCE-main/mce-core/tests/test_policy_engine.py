"""
MCE — Policy Engine Tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.policy_engine import PolicyEngine, PolicyDecision
from schemas.mce_config import PolicyConfig


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine(PolicyConfig(
        blocked_commands=["rm -rf", "mkfs"],
        blocked_network=["0.0.0.0", "169.254."],
        hitl_commands=["DROP", "TRUNCATE"],
    ))


class TestBlockedCommands:
    def test_blocks_exact_match(self, engine: PolicyEngine):
        result = engine.check("bash", "rm -rf /")
        assert result.decision == PolicyDecision.BLOCK
        assert "rm -rf" in result.matched_rule

    def test_blocks_case_insensitive(self, engine: PolicyEngine):
        result = engine.check("bash", "MKFS /dev/sda")
        assert result.decision == PolicyDecision.BLOCK

    def test_allows_safe_command(self, engine: PolicyEngine):
        result = engine.check("bash", "ls -la")
        assert result.decision == PolicyDecision.ALLOW

    def test_blocks_in_dict_payload(self, engine: PolicyEngine):
        result = engine.check("bash", {"command": "rm -rf /home"})
        assert result.decision == PolicyDecision.BLOCK


class TestBlockedNetwork:
    def test_blocks_forbidden_ip(self, engine: PolicyEngine):
        result = engine.check("curl", "http://0.0.0.0:8080")
        assert result.decision == PolicyDecision.BLOCK

    def test_blocks_link_local(self, engine: PolicyEngine):
        result = engine.check("curl", "http://169.254.1.1")
        assert result.decision == PolicyDecision.BLOCK

    def test_allows_safe_url(self, engine: PolicyEngine):
        result = engine.check("curl", "http://example.com")
        assert result.decision == PolicyDecision.ALLOW


class TestHitL:
    def test_triggers_hitl(self, engine: PolicyEngine):
        result = engine.check("sql", "DROP TABLE users;")
        assert result.decision == PolicyDecision.HITL
        assert "DROP" in result.matched_rule

    def test_hitl_requires_approval(self, engine: PolicyEngine):
        result = engine.check("sql", "TRUNCATE logs;")
        assert result.decision == PolicyDecision.HITL


class TestToText:
    def test_string_passthrough(self, engine: PolicyEngine):
        assert engine._to_text("hello") == "hello"

    def test_dict_json(self, engine: PolicyEngine):
        text = engine._to_text({"a": 1})
        assert '"a": 1' in text

    def test_other_str(self, engine: PolicyEngine):
        assert engine._to_text(123) == "123"
