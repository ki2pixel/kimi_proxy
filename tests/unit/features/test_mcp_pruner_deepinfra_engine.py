from __future__ import annotations

import re

import httpx
import pytest

from kimi_proxy.features.mcp_pruner.deepinfra_client import DeepInfraClient
from kimi_proxy.features.mcp_pruner.deepinfra_engine import prune_text_with_deepinfra


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_engine_respects_min_keep_and_markers_not_annotated() -> None:
    # 10 lignes => avec max_prune_ratio=0.6 => keep ceil(10*0.4)=4; min_keep_lines=3 => keep=4
    text = "\n".join([f"L{i}" for i in range(1, 11)])

    # Scores => garder indices 0, 1, 2, 3 (top-4)
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"scores": [10, 9, 8, 7, 0, 0, 0, 0, 0, 0]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        deepinfra_client = DeepInfraClient(
            config=_dummy_deepinfra_cfg(),
            http_client=http_client,
        )
        async with deepinfra_client:
            out = await prune_text_with_deepinfra(
                prune_id="prn_test",
                text=text,
                goal_hint="keep L1",
                source_type="docs",
                max_prune_ratio=0.6,
                min_keep_lines=3,
                annotate_lines=True,
                include_markers=True,
                max_docs=64,
                deepinfra_client=deepinfra_client,
            )

    # Lignes conservées annotées, markers non annotés
    for line in out.pruned_text.splitlines():
        if line.startswith("⟦PRUNÉ:"):
            assert not re.match(r"^\d+│\s+⟦PRUNÉ:", line)
        else:
            assert re.match(r"^\d+│\s+", line)

    stats = out.stats
    assert stats.get("backend") == "deepinfra"
    assert stats.get("kept_lines") == 4
    assert stats.get("pruned_lines") == 6

    anns = out.annotations
    assert isinstance(anns, list)
    # Au moins un bloc pruné (ligne 5-10)
    assert any(a.get("original_start_line") == 5 and a.get("original_end_line") == 10 for a in anns if isinstance(a, dict))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deepinfra_engine_respects_max_prune_ratio() -> None:
    # 5 lignes, max_prune_ratio=0.2 => keep ceil(5*0.8)=4
    text = "\n".join(["a", "b", "c", "d", "e"])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"scores": [0, 1, 2, 3, 4]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        deepinfra_client = DeepInfraClient(config=_dummy_deepinfra_cfg(), http_client=http_client)
        async with deepinfra_client:
            out = await prune_text_with_deepinfra(
                prune_id="prn_test",
                text=text,
                goal_hint="goal",
                source_type="docs",
                max_prune_ratio=0.2,
                min_keep_lines=0,
                annotate_lines=False,
                include_markers=False,
                max_docs=64,
                deepinfra_client=deepinfra_client,
            )

    assert out.stats.get("kept_lines") == 4
    assert out.stats.get("pruned_lines") == 1


def _dummy_deepinfra_cfg():
    # Import local pour éviter une dépendance sur env vars dans ces tests.
    from kimi_proxy.features.mcp_pruner.deepinfra_client import DeepInfraClientConfig

    return DeepInfraClientConfig(
        endpoint_url="https://api.deepinfra.com/v1/inference/Qwen/Qwen3-Reranker-0.6B",
        api_key="test",
        timeout_ms=1000,
        max_docs=64,
    )
