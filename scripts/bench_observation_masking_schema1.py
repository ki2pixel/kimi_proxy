"""Benchmark offline — Observation Masking Schéma 1.

But:
- Mesurer le gain tokens/chars avant/après masking Schéma 1 sur une fixture.

Contraintes:
- Zéro réseau
- Complexité O(n)
- Output stable (option --json)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

# Permet d'exécuter le script sans installer le package
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from kimi_proxy.core.tokens import count_tokens_tiktoken
from kimi_proxy.features.observation_masking.schema1 import MaskPolicy, mask_old_tool_results


@dataclass(frozen=True)
class BenchResult:
    window_turns: int
    masked_tool_results: int
    tool_chars_before: int
    tool_chars_after: int
    tokens_before: int
    tokens_after: int


def _sum_tool_chars(messages: list[dict[str, object]]) -> int:
    total = 0
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
    return total


def _count_masked_tool_results(before: list[dict[str, object]], after: list[dict[str, object]]) -> int:
    masked = 0
    for b, a in zip(before, after):
        if b.get("role") != "tool":
            continue
        if not isinstance(b.get("content"), str):
            continue
        if not isinstance(a.get("content"), str):
            continue
        if a.get("content") != b.get("content"):
            masked += 1
    return masked


def run_benchmark(*, fixture_path: Path, window_turns: int, json_output: bool) -> int:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    messages_obj = payload.get("messages")
    if not isinstance(messages_obj, list):
        raise ValueError("Fixture invalide: clé 'messages' manquante ou non-list")

    # Normalise en list[dict[str, object]] sans Any
    messages: list[dict[str, object]] = [m for m in messages_obj if isinstance(m, dict)]

    tokens_before = count_tokens_tiktoken(messages)
    tool_chars_before = _sum_tool_chars(messages)

    policy = MaskPolicy(enabled=True, window_turns=window_turns, keep_errors=True)
    masked_messages = mask_old_tool_results(messages, policy)

    tokens_after = count_tokens_tiktoken(masked_messages)
    tool_chars_after = _sum_tool_chars(masked_messages)
    masked_tool_results = _count_masked_tool_results(messages, masked_messages)

    result = BenchResult(
        window_turns=window_turns,
        masked_tool_results=masked_tool_results,
        tool_chars_before=tool_chars_before,
        tool_chars_after=tool_chars_after,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
    )

    if json_output:
        print(json.dumps(asdict(result), ensure_ascii=False))
    else:
        delta_tokens = tokens_before - tokens_after
        delta_chars = tool_chars_before - tool_chars_after
        ratio_tokens = (tokens_after / tokens_before) if tokens_before > 0 else 1.0
        print("Benchmark Observation Masking Schéma 1")
        print(f"Fixture: {fixture_path}")
        print(f"window_turns: {window_turns}")
        print(f"tool_results masqués: {masked_tool_results}")
        print(f"tool chars: {tool_chars_before} -> {tool_chars_after} (delta={delta_chars})")
        print(f"tokens: {tokens_before} -> {tokens_after} (delta={delta_tokens}, ratio={ratio_tokens:.3f})")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/schema1_tool_heavy.json"),
        help="Chemin vers la fixture JSON (défaut: tests/fixtures/schema1_tool_heavy.json)",
    )
    parser.add_argument(
        "--window-turns",
        type=int,
        default=1,
        help="Nombre de tours tool à conserver intacts (défaut: 1)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie JSON stable (utile CI)",
    )
    args = parser.parse_args()

    return run_benchmark(fixture_path=args.fixture, window_turns=max(0, args.window_turns), json_output=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
