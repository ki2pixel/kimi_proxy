"""kimi_proxy.features.mcp_tool_pruning.metrics

Collecteur de métriques **metadata-only** pour le pruning des outputs MCP tools/call.

Contraintes:
- Ne jamais stocker ni exposer de texte/payload.
- Conçu pour être attaché aux services (gateway, bridge) et exposé via /health
  (si activé) ou stderr côté bridge.

Note:
- Cette couche est "Features" (sans I/O). Les export vers stderr/HTTP sont
  effectués dans API/scripts.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class MCPToolPruningMetricsSnapshot:
    calls_total: int

    skipped_disabled: int
    skipped_invalid_request: int
    skipped_non_tools_call: int
    skipped_server_pruner: int
    skipped_tool_excluded: int

    skipped_invalid_response: int
    skipped_error_response: int
    skipped_no_content: int

    eligible_total: int
    responses_changed: int

    pruner_calls_total: int
    pruner_calls_ok: int
    pruner_calls_fail: int
    pruner_calls_exception: int

    fail_open_total: int
    fallback_mask_total: int

    texts_examined: int
    texts_over_threshold: int
    texts_pruned: int

    chars_before_total: int
    chars_after_total: int

    elapsed_ms_total: int
    elapsed_ms_max: int


class MCPToolPruningMetricsCollector:
    """Collecteur in-memory, thread-safe (async).

    Toutes les valeurs sont des compteurs/latences (ints) uniquement.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        self._calls_total = 0

        self._skipped_disabled = 0
        self._skipped_invalid_request = 0
        self._skipped_non_tools_call = 0
        self._skipped_server_pruner = 0
        self._skipped_tool_excluded = 0

        self._skipped_invalid_response = 0
        self._skipped_error_response = 0
        self._skipped_no_content = 0

        self._eligible_total = 0
        self._responses_changed = 0

        self._pruner_calls_total = 0
        self._pruner_calls_ok = 0
        self._pruner_calls_fail = 0
        self._pruner_calls_exception = 0

        self._fail_open_total = 0
        self._fallback_mask_total = 0

        self._texts_examined = 0
        self._texts_over_threshold = 0
        self._texts_pruned = 0

        self._chars_before_total = 0
        self._chars_after_total = 0

        self._elapsed_ms_total = 0
        self._elapsed_ms_max = 0

    async def record_call(self) -> None:
        async with self._lock:
            self._calls_total += 1

    async def record_skip(self, reason: str) -> None:
        async with self._lock:
            if reason == "disabled":
                self._skipped_disabled += 1
            elif reason == "invalid_request":
                self._skipped_invalid_request += 1
            elif reason == "non_tools_call":
                self._skipped_non_tools_call += 1
            elif reason == "server_pruner":
                self._skipped_server_pruner += 1
            elif reason == "tool_excluded":
                self._skipped_tool_excluded += 1
            elif reason == "invalid_response":
                self._skipped_invalid_response += 1
            elif reason == "error_response":
                self._skipped_error_response += 1
            elif reason == "no_content":
                self._skipped_no_content += 1

    async def record_eligible(self) -> None:
        async with self._lock:
            self._eligible_total += 1

    async def record_response_changed(self) -> None:
        async with self._lock:
            self._responses_changed += 1

    async def record_text_examined(self, *, length_chars: int, over_threshold: bool) -> None:
        async with self._lock:
            self._texts_examined += 1
            if over_threshold:
                self._texts_over_threshold += 1
            if length_chars > 0:
                self._chars_before_total += int(length_chars)

    async def record_text_after(self, *, length_chars: int, pruned: bool) -> None:
        async with self._lock:
            if pruned:
                self._texts_pruned += 1
            if length_chars > 0:
                self._chars_after_total += int(length_chars)

    async def record_pruner_call(self, *, ok: bool, had_exception: bool) -> None:
        async with self._lock:
            self._pruner_calls_total += 1
            if had_exception:
                self._pruner_calls_exception += 1
            if ok:
                self._pruner_calls_ok += 1
            else:
                self._pruner_calls_fail += 1

    async def record_fail_open(self) -> None:
        async with self._lock:
            self._fail_open_total += 1

    async def record_fallback_mask(self) -> None:
        async with self._lock:
            self._fallback_mask_total += 1

    async def record_elapsed_ms(self, elapsed_ms: int) -> None:
        ms = max(0, int(elapsed_ms))
        async with self._lock:
            self._elapsed_ms_total += ms
            if ms > self._elapsed_ms_max:
                self._elapsed_ms_max = ms

    async def snapshot(self) -> MCPToolPruningMetricsSnapshot:
        async with self._lock:
            return MCPToolPruningMetricsSnapshot(
                calls_total=int(self._calls_total),
                skipped_disabled=int(self._skipped_disabled),
                skipped_invalid_request=int(self._skipped_invalid_request),
                skipped_non_tools_call=int(self._skipped_non_tools_call),
                skipped_server_pruner=int(self._skipped_server_pruner),
                skipped_tool_excluded=int(self._skipped_tool_excluded),
                skipped_invalid_response=int(self._skipped_invalid_response),
                skipped_error_response=int(self._skipped_error_response),
                skipped_no_content=int(self._skipped_no_content),
                eligible_total=int(self._eligible_total),
                responses_changed=int(self._responses_changed),
                pruner_calls_total=int(self._pruner_calls_total),
                pruner_calls_ok=int(self._pruner_calls_ok),
                pruner_calls_fail=int(self._pruner_calls_fail),
                pruner_calls_exception=int(self._pruner_calls_exception),
                fail_open_total=int(self._fail_open_total),
                fallback_mask_total=int(self._fallback_mask_total),
                texts_examined=int(self._texts_examined),
                texts_over_threshold=int(self._texts_over_threshold),
                texts_pruned=int(self._texts_pruned),
                chars_before_total=int(self._chars_before_total),
                chars_after_total=int(self._chars_after_total),
                elapsed_ms_total=int(self._elapsed_ms_total),
                elapsed_ms_max=int(self._elapsed_ms_max),
            )
