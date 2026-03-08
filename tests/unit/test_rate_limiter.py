from __future__ import annotations

import pytest

from kimi_proxy.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_throttle_if_needed_counts_request_only_once_when_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RateLimiter(max_rpm=2)
    limiter.requests.append(99.0)

    monkeypatch.setattr("kimi_proxy.services.rate_limiter.time.time", lambda: 100.0)

    async def _fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("kimi_proxy.services.rate_limiter.asyncio.sleep", _fake_sleep)

    status = await limiter.throttle_if_needed()

    assert status["current_rpm"] == 2
    assert len(limiter.requests) == 2