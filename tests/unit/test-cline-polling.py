"""Tests unitaires — Polling Cline (ledger local) + broadcast WS.

Notes:
    - Le polling appelle ClineImporter.get_latest_ts() + import_default_ledger()
    - Le broadcast est envoyé uniquement quand le latest_ts change.
"""

from __future__ import annotations

import pytest

from kimi_proxy.services.cline_polling import (
    ClinePollingConfig,
    ClinePollingService,
)


class _FakeManager:
    def __init__(self):
        self.messages = []

    async def broadcast(self, message):
        self.messages.append(message)


class _FakeImporter:
    def __init__(self, before_ts, after_ts, imported_count=1):
        self._before_ts = before_ts
        self._after_ts = after_ts
        self._imported_count = imported_count
        self._calls = 0
        self._count_calls = 0

    async def get_latest_ts(self):
        # 1er appel = before, 2e appel = after
        self._calls += 1
        return self._before_ts if self._calls == 1 else self._after_ts

    async def import_default_ledger(self):
        return {
            "imported_count": self._imported_count,
            "skipped_count": 0,
            "error_count": 0,
            "latest_ts": self._after_ts,
        }

    async def get_usage_count(self):
        # 1er appel = before, 2e appel = after
        self._count_calls += 1
        if self._count_calls == 1:
            return 10
        return 10 if self._after_ts == self._before_ts else 11


@pytest.mark.asyncio
async def test_poll_once_no_change_no_broadcast():
    manager = _FakeManager()
    importer = _FakeImporter(before_ts=123, after_ts=123)
    service = ClinePollingService(
        manager=manager,
        importer=importer,
        config=ClinePollingConfig(enabled=True, interval_seconds=1.0, backoff_max_seconds=10.0),
    )

    sent = await service.poll_once()
    assert sent is False
    assert manager.messages == []


@pytest.mark.asyncio
async def test_poll_once_change_sends_broadcast():
    manager = _FakeManager()
    importer = _FakeImporter(before_ts=100, after_ts=200, imported_count=3)
    service = ClinePollingService(
        manager=manager,
        importer=importer,
        config=ClinePollingConfig(enabled=True, interval_seconds=1.0, backoff_max_seconds=10.0),
    )

    sent = await service.poll_once()
    assert sent is True
    assert len(manager.messages) == 1
    msg = manager.messages[0]
    assert msg["type"] == "cline_usage_updated"
    assert msg["latest_ts"] == 200
    assert msg["latest_count"] >= 0
    assert msg["imported_count"] == 3
    assert "timestamp" in msg
