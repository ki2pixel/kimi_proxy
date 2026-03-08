import pytest

from kimi_proxy.proxy.router import map_model_name


def test_map_model_name_supports_exact_deepseek_nvidia_alias() -> None:
    models = {
        "nvidia/deepseek-v3.2": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v3.2",
        },
        "deepseek-ai/deepseek-v3.2": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v3.2",
        },
    }

    assert map_model_name("deepseek-ai/deepseek-v3.2", models) == "deepseek-ai/deepseek-v3.2"


@pytest.mark.parametrize(
    ("client_model", "expected_model"),
    [
        ("moonshotai/kimi-k2.5", "moonshotai/kimi-k2.5"),
        ("moonshotai/kimi-k2-thinking", "moonshotai/kimi-k2-thinking"),
        ("openai/gpt-oss-120b", "openai/gpt-oss-120b"),
        ("deepseek-ai/deepseek-v3.2", "deepseek-ai/deepseek-v3.2"),
        ("z-ai/glm4.7", "z-ai/glm4.7"),
        ("z-ai/glm5", "z-ai/glm5"),
        ("mistralai/mistral-large-3-675b-instruct-2512", "mistralai/mistral-large-3-675b-instruct-2512"),
        ("qwen/qwen3-next-80b-a3b-thinking", "qwen/qwen3-next-80b-a3b-thinking"),
    ],
)
def test_map_model_name_keeps_exact_upstream_identifier_when_known(
    client_model: str,
    expected_model: str,
) -> None:
    models = {
        "nvidia/kimi-k2.5": {
            "provider": "nvidia",
            "model": "moonshotai/kimi-k2.5",
        },
        "nvidia/kimi-k2-thinking": {
            "provider": "nvidia",
            "model": "moonshotai/kimi-k2-thinking",
        },
        "nvidia/gpt-oss-120b": {
            "provider": "nvidia",
            "model": "openai/gpt-oss-120b",
        },
        "nvidia/deepseek-v3.2": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v3.2",
        },
        "nvidia/glm-4.7": {
            "provider": "nvidia",
            "model": "z-ai/glm4.7",
        },
        "nvidia/glm-5": {
            "provider": "nvidia",
            "model": "z-ai/glm5",
        },
        "nvidia/mistral-large-3-675b": {
            "provider": "nvidia",
            "model": "mistralai/mistral-large-3-675b-instruct-2512",
        },
        "nvidia/qwen3-next-80b-a3b-thinking": {
            "provider": "nvidia",
            "model": "qwen/qwen3-next-80b-a3b-thinking",
        },
    }

    assert map_model_name(client_model, models) == expected_model


def test_map_model_name_keeps_simple_suffix_fallback_when_alias_missing() -> None:
    models = {
        "nvidia/deepseek-v3.2": {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v3.2",
        }
    }

    assert map_model_name("foo/bar", models) == "bar"