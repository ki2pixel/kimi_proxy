"""
MCE — Circuit Breaker Tests
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.circuit_breaker import CircuitBreaker
from schemas.mce_config import CircuitBreakerConfig


@pytest.fixture
def breaker() -> CircuitBreaker:
    return CircuitBreaker(CircuitBreakerConfig(window_size=5, failure_threshold=3))


class TestCircuitBreaker:
    def test_no_trip_on_success(self, breaker: CircuitBreaker):
        for _ in range(5):
            state = breaker.record("tool_a", {"x": 1}, is_error=False)
            assert not state.is_tripped

    def test_no_trip_on_different_errors(self, breaker: CircuitBreaker):
        breaker.record("tool_a", {"x": 1}, is_error=True)
        breaker.record("tool_a", {"x": 2}, is_error=True)
        breaker.record("tool_a", {"x": 3}, is_error=True)
        state = breaker.record("tool_a", {"x": 4}, is_error=True)
        # Different args = different fingerprints, so no trip
        assert not state.is_tripped

    def test_trip_on_identical_errors(self, breaker: CircuitBreaker):
        args = {"x": 1}
        breaker.record("tool_a", args, is_error=True)
        breaker.record("tool_a", args, is_error=True)
        state = breaker.record("tool_a", args, is_error=True)
        assert state.is_tripped
        assert "stuck in a loop" in state.alert_message

    def test_success_resets_failure_window(self, breaker: CircuitBreaker):
        args = {"x": 1}
        breaker.record("tool_a", args, is_error=True)
        breaker.record("tool_a", args, is_error=True)
        # Success has a different fingerprint, but old failures remain in window.
        # We need enough successes to push the old errors out of the 5-slot window.
        breaker.record("tool_a", args, is_error=False)
        breaker.record("tool_a", args, is_error=False)
        breaker.record("tool_a", args, is_error=False)
        state = breaker.record("tool_a", args, is_error=True)
        assert not state.is_tripped

    def test_unrelated_tools_do_not_cause_trip(self, breaker: CircuitBreaker):
        args = {"x": 1}
        # Fill window with unrelated failures that have DIFFERENT fingerprints
        for i in range(5):
            breaker.record("other_tool", {"i": i}, is_error=True)
        # Only 2 tool_a failures — should NOT trip (threshold is 3)
        breaker.record("tool_a", args, is_error=True)
        state = breaker.record("tool_a", args, is_error=True)
        assert not state.is_tripped

    def test_reset_clears_window(self, breaker: CircuitBreaker):
        args = {"x": 1}
        breaker.record("tool_a", args, is_error=True)
        breaker.record("tool_a", args, is_error=True)
        breaker.reset()
        state = breaker.record("tool_a", args, is_error=True)
        assert not state.is_tripped

    def test_window_property(self, breaker: CircuitBreaker):
        breaker.record("tool_a", {"x": 1}, is_error=False)
        assert len(breaker.window) == 1

    def test_trip_on_fuzzy_similar_errors(self, breaker: CircuitBreaker):
        breaker.record(
            "run_command",
            {"command": "pytest tests/test_integrations.py -v --tb=short"},
            is_error=True,
        )
        breaker.record(
            "run_command",
            {"command": "pytest  tests/test_integrations.py  -v  --tb=short"},
            is_error=True,
        )
        state = breaker.record(
            "run_command",
            {"command": "pytest tests/test_integrations.py -v --tb=short --force"},
            is_error=True,
        )
        assert state.is_tripped
        assert "stuck in a loop" in state.alert_message
