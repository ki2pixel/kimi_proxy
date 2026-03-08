from __future__ import annotations

import json

from kimi_proxy.proxy.tool_utils import normalize_tool_call_arguments


def test_normalize_tool_call_arguments_repairs_malformed_json_string() -> None:
    body = {
        "messages": [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "fast_read_file",
                            "arguments": '{"query":"abc" "limit":3}',
                        },
                    }
                ],
            }
        ]
    }

    normalized_body, fixed_count = normalize_tool_call_arguments(body)

    assert fixed_count == 1
    arguments = normalized_body["messages"][0]["tool_calls"][0]["function"]["arguments"]
    assert json.loads(arguments) == {"query": "abc", "limit": 3}


def test_normalize_tool_call_arguments_serializes_dict_arguments() -> None:
    body = {
        "messages": [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "fast_read_file",
                            "arguments": {"path": "/tmp/demo.txt", "recursive": False},
                        },
                    }
                ],
            }
        ]
    }

    normalized_body, fixed_count = normalize_tool_call_arguments(body)

    assert fixed_count == 1
    arguments = normalized_body["messages"][0]["tool_calls"][0]["function"]["arguments"]
    assert isinstance(arguments, str)
    assert json.loads(arguments) == {"path": "/tmp/demo.txt", "recursive": False}