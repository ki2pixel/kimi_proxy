from __future__ import annotations

import pytest

from kimi_proxy.features.observation_masking.schema1 import MaskPolicy, mask_old_tool_results


def _make_assistant_tool_turn(*, call_ids: list[str], tool_name: str = "fast_read_file") -> dict[str, object]:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": "{}"},
            }
            for call_id in call_ids
        ],
    }


def _make_tool_result(*, tool_call_id: str, content: object) -> dict[str, object]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


def test_mask_old_tool_results_disabled_returns_same_object():
    messages = [
        {"role": "user", "content": "hello"},
        _make_assistant_tool_turn(call_ids=["call_1"]),
        _make_tool_result(tool_call_id="call_1", content="OK"),
    ]

    policy = MaskPolicy(enabled=False, window_turns=1)
    out = mask_old_tool_results(messages, policy)

    assert out is messages


def test_mask_old_tool_results_preserves_invariants_and_masks_old_turns():
    # 2 tool turns: keep only last one.
    messages = [
        {"role": "system", "content": "S"},
        _make_assistant_tool_turn(call_ids=["call_1"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content="A" * 1000),
        {"role": "user", "content": "next"},
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_search_files"),
        _make_tool_result(tool_call_id="call_2", content="B" * 1000),
    ]

    policy = MaskPolicy(enabled=True, window_turns=1, keep_errors=True)
    out = mask_old_tool_results(messages, policy)

    assert out is not messages
    assert len(out) == len(messages)
    assert [m.get("role") for m in out] == [m.get("role") for m in messages]

    # tool_call_id preserved
    assert out[2].get("tool_call_id") == "call_1"
    assert out[5].get("tool_call_id") == "call_2"

    # assistant tool_calls unchanged
    assert out[1].get("tool_calls") == messages[1].get("tool_calls")
    assert out[4].get("tool_calls") == messages[4].get("tool_calls")

    # old tool result masked, recent kept
    masked_content = out[2].get("content")
    assert isinstance(masked_content, str)
    assert "Observation masquée" in masked_content
    assert "call_1" in masked_content

    assert out[5].get("content") == messages[5].get("content")


def test_keep_errors_preserves_traceback_like_content():
    messages = [
        _make_assistant_tool_turn(call_ids=["call_1"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content="Traceback (most recent call last): ..."),
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_2", content="OK"),
    ]

    policy = MaskPolicy(enabled=True, window_turns=1, keep_errors=True)
    out = mask_old_tool_results(messages, policy)

    # call_1 is old (window=1 keeps call_2), but is error -> not masked
    assert out[1].get("content") == messages[1].get("content")


def test_orphan_tool_result_is_not_masked_by_default():
    messages = [
        {"role": "user", "content": "hello"},
        _make_tool_result(tool_call_id="orphan", content="SHOULD_STAY"),
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_2", content="OK"),
    ]

    policy = MaskPolicy(enabled=True, window_turns=1)
    out = mask_old_tool_results(messages, policy)

    assert out[1].get("content") == "SHOULD_STAY"


def test_keep_last_k_per_tool_keeps_last_result_per_tool():
    messages = [
        _make_assistant_tool_turn(call_ids=["call_1"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content="A" * 1000),
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_2", content="B" * 1000),
        _make_assistant_tool_turn(call_ids=["call_3"], tool_name="fast_search_files"),
        _make_tool_result(tool_call_id="call_3", content="C" * 1000),
    ]

    # Keep only last turn normally => call_1 and call_2 would be masked.
    # With keep_last_k_per_tool=1 => keep last fast_read_file (call_2) even if old.
    policy = MaskPolicy(enabled=True, window_turns=1, keep_last_k_per_tool=1)
    out = mask_old_tool_results(messages, policy)

    assert isinstance(out[1].get("content"), str)  # call_1 masked
    assert out[3].get("content") == messages[3].get("content")  # call_2 kept
    assert out[5].get("content") == messages[5].get("content")  # call_3 kept (window)


def test_multi_tool_calls_in_same_turn_are_masked_together():
    # 2 tool turns, first turn has 2 tool calls.
    messages = [
        _make_assistant_tool_turn(call_ids=["call_1", "call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content="A" * 1000),
        _make_tool_result(tool_call_id="call_2", content="B" * 1000),
        _make_assistant_tool_turn(call_ids=["call_3"], tool_name="fast_search_files"),
        _make_tool_result(tool_call_id="call_3", content="OK"),
    ]

    policy = MaskPolicy(enabled=True, window_turns=1)
    out = mask_old_tool_results(messages, policy)

    assert len(out) == len(messages)
    # call_1 + call_2 old => masked
    assert isinstance(out[1].get("content"), str)
    assert isinstance(out[2].get("content"), str)
    assert "call_1" in str(out[1].get("content"))
    assert "call_2" in str(out[2].get("content"))
    # call_3 in window => kept
    assert out[4].get("content") == "OK"


def test_non_string_tool_content_is_not_masked_even_if_old():
    # content list => no-op per spec.
    messages = [
        _make_assistant_tool_turn(call_ids=["call_1"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content=[{"type": "text", "text": "HELLO"}]),
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_2", content="OK"),
    ]

    policy = MaskPolicy(enabled=True, window_turns=1)
    out = mask_old_tool_results(messages, policy)

    assert out[1].get("content") == messages[1].get("content")


def test_keep_errors_preserves_json_error_payload():
    messages = [
        _make_assistant_tool_turn(call_ids=["call_1"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content='{"error": "boom"}'),
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_2", content="OK"),
    ]

    policy = MaskPolicy(enabled=True, window_turns=1, keep_errors=True)
    out = mask_old_tool_results(messages, policy)

    # call_1 is old but looks like JSON error => keep
    assert out[1].get("content") == messages[1].get("content")


def test_window_turns_bigger_than_turns_masks_nothing():
    messages = [
        _make_assistant_tool_turn(call_ids=["call_1"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_1", content="A" * 1000),
        _make_assistant_tool_turn(call_ids=["call_2"], tool_name="fast_read_file"),
        _make_tool_result(tool_call_id="call_2", content="B" * 1000),
    ]

    policy = MaskPolicy(enabled=True, window_turns=10)
    out = mask_old_tool_results(messages, policy)

    assert out[1].get("content") == messages[1].get("content")
    assert out[3].get("content") == messages[3].get("content")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
