from __future__ import annotations

import pytest

from kimi_proxy.features.pruner_goal_hint import GoalHintConfig, derive_goal_hint


def test_derive_goal_hint_extracts_plan_bullets() -> None:
    messages = [
        {"role": "system", "content": "Tu es un assistant."},
        {
            "role": "user",
            "content": "Plan:\n- Corriger le bug de streaming\n- Ajouter des tests\n- Déployer",
        },
        {"role": "assistant", "content": "OK"},
    ]

    hint = derive_goal_hint(messages)
    assert "Corriger le bug de streaming" in hint
    assert "Ajouter des tests" in hint


def test_derive_goal_hint_falls_back_to_last_user() -> None:
    messages = [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut"},
        {"role": "user", "content": "Intègre le pruner dans /chat/completions"},
    ]
    hint = derive_goal_hint(messages)
    assert hint == "Intègre le pruner dans /chat/completions"


def test_derive_goal_hint_empty_returns_default() -> None:
    messages = [
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": ""},
    ]
    cfg = GoalHintConfig(default_goal_hint="fallback")
    hint = derive_goal_hint(messages, cfg)
    assert hint == "fallback"


def test_derive_goal_hint_ignores_non_string_content() -> None:
    messages = [
        {"role": "user", "content": {"type": "text", "text": "Plan: do x"}},
        {"role": "user", "content": ["Plan:", "- x"]},
    ]
    cfg = GoalHintConfig(default_goal_hint="fallback")
    hint = derive_goal_hint(messages, cfg)
    assert hint == "fallback"


def test_derive_goal_hint_truncates_max_chars() -> None:
    messages = [
        {"role": "user", "content": "A" * 1000},
    ]
    cfg = GoalHintConfig(max_chars=100)
    hint = derive_goal_hint(messages, cfg)
    assert len(hint) == 100
