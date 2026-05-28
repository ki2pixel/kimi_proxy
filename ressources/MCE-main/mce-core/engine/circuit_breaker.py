"""
MCE — Circuit Breaker
Detects infinite loops: if the agent calls the same tool with the same
failing arguments 3 times, MCE trips the breaker and forces a context shift.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from schemas.mce_config import CircuitBreakerConfig
from utils.logger import get_logger

_log = get_logger("CircuitBreaker")


# ──────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    """A single tool invocation record for the sliding window."""
    tool_name: str
    arguments_hash: str
    is_error: bool
    fingerprint: str  # hash(tool + args + error_flag)
    arguments: Optional[dict[str, Any]] = None


@dataclass
class BreakerState:
    """Current state of the circuit breaker."""
    is_tripped: bool = False
    consecutive_failures: int = 0
    alert_message: str = ""


# ──────────────────────────────────────────────
# Circuit Breaker
# ──────────────────────────────────────────────

class CircuitBreaker:
    """
    Sliding-window loop detector.

    Maintains the last N tool calls. If the same tool+args combination
    fails >= threshold times, trips the breaker.
    """

    ALERT_TEMPLATE = (
        "[MCE Alert: You are stuck in a loop. "
        "Previous {count} attempts failed identically. "
        "Pause execution and formulate a completely different approach, "
        "or ask the user for help.]"
    )

    def __init__(self, config: CircuitBreakerConfig | None = None):
        cfg = config or CircuitBreakerConfig()
        self._window_size = cfg.window_size
        self._threshold = cfg.failure_threshold
        self._window: deque[ToolCallRecord] = deque(maxlen=self._window_size)
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────

    def record(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        is_error: bool = False,
    ) -> BreakerState:
        """
        Record a tool call and check for loops.

        Returns BreakerState — check .is_tripped to see if the
        breaker has been activated.
        """
        args_hash = self._hash_args(arguments)
        fingerprint = hashlib.sha256(
            f"{tool_name}:{args_hash}:{is_error}".encode()
        ).hexdigest()[:16]

        with self._lock:
            record = ToolCallRecord(
                tool_name=tool_name,
                arguments_hash=args_hash,
                is_error=is_error,
                fingerprint=fingerprint,
                arguments=arguments,
            )
            self._window.append(record)

            # Count similar failing tool calls in current window using fuzzy matching
            if is_error:
                count = 0
                for r in self._window:
                    if r.tool_name == tool_name and r.is_error:
                        if self._jaccard_similarity(r.arguments, arguments) >= 0.85:
                            count += 1

                if count >= self._threshold:
                    alert = self.ALERT_TEMPLATE.format(count=count)
                    _log.warning(
                        f"[mce.error]BREAKER TRIPPED[/mce.error]: "
                        f"{tool_name} failed {count}× with similar/identical arguments"
                    )
                    return BreakerState(
                        is_tripped=True,
                        consecutive_failures=count,
                        alert_message=alert,
                    )

            return BreakerState(is_tripped=False)

    def _get_tokens(self, arguments: Optional[dict[str, Any]]) -> set[str]:
        if not arguments:
            return set()
        # Serialize to lowercase string
        serialized = json.dumps(arguments, sort_keys=True, default=str).lower()
        # Find all alphanumeric/word tokens
        return set(re.findall(r"\w+", serialized))

    def _jaccard_similarity(self, args1: Optional[dict[str, Any]], args2: Optional[dict[str, Any]]) -> float:
        tokens1 = self._get_tokens(args1)
        tokens2 = self._get_tokens(args2)
        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0
        return len(tokens1 & tokens2) / len(tokens1 | tokens2)

    def reset(self) -> None:
        """Clear the sliding window."""
        with self._lock:
            self._window.clear()

    @property
    def window(self) -> list[ToolCallRecord]:
        """Current window contents (for observability)."""
        with self._lock:
            return list(self._window)

    # ── Internal ──────────────────────────────

    @staticmethod
    def _hash_args(arguments: Optional[dict[str, Any]]) -> str:
        canonical = json.dumps(arguments or {}, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
