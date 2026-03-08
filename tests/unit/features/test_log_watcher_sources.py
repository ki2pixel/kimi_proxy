from __future__ import annotations

from pathlib import Path
import json

import pytest

from kimi_proxy.core.models import TokenMetrics
from kimi_proxy.features.log_watcher import (
    ContinueLogSource,
    KimiGlobalLogSource,
    KimiSessionSource,
    LogWatcher,
    create_log_watcher,
)
from kimi_proxy.main import _format_log_error_message, _should_emit_error_log


@pytest.mark.asyncio
async def test_continue_log_source_reads_only_new_lines(tmp_path: Path) -> None:
    log_file = tmp_path / "core.log"
    log_file.write_text("historique\n", encoding="utf-8")

    source = ContinueLogSource(log_path=str(log_file))
    await source.initialize()

    log_file.write_text(
        "historique\nprompt tokens: 42\ncompletion tokens: 8\n",
        encoding="utf-8",
    )

    events = await source.poll()

    assert len(events) == 2
    assert events[0].metrics.prompt_tokens == 42
    assert events[0].metrics.completion_tokens == 0
    assert events[1].metrics.prompt_tokens == 0
    assert events[1].metrics.completion_tokens == 8
    assert all(event.metrics.source == "continue_logs" for event in events)


def test_create_log_watcher_uses_continue_source_by_default(tmp_path: Path) -> None:
    log_file = tmp_path / "core.log"
    watcher = create_log_watcher(log_path=str(log_file))

    assert isinstance(watcher, LogWatcher)
    assert len(watcher.sources) == 3
    assert isinstance(watcher.sources[0], ContinueLogSource)
    assert isinstance(watcher.sources[1], KimiGlobalLogSource)
    assert isinstance(watcher.sources[2], KimiSessionSource)
    assert watcher.log_path == str(log_file)


@pytest.mark.asyncio
async def test_kimi_global_log_source_parses_model_and_error_without_leaking_secrets(tmp_path: Path) -> None:
    log_file = tmp_path / "kimi.log"
    log_file.write_text("bootstrap\n", encoding="utf-8")

    source = KimiGlobalLogSource(log_path=str(log_file))
    await source.initialize()

    log_file.write_text(
        "bootstrap\n"
        "2026-03-07 11:01:38.134 | INFO     | kimi_cli.app:create:155 - Using LLM model: provider='managed:kimi-code' model='kimi-for-coding' max_context_size=262144 capabilities={'thinking'}\n"
        "2026-03-07 11:01:39.772 | ERROR    | threading:run:1024 - node:internal/modules/cjs/loader:1210\n",
        encoding="utf-8",
    )

    events = await source.poll()

    assert len(events) == 2
    assert events[0].provider == "managed:kimi-code"
    assert events[0].model == "kimi-for-coding"
    assert events[0].metrics.context_length == 262144
    assert events[0].preview == "Modèle actif: managed:kimi-code/kimi-for-coding"
    assert events[1].metrics.is_api_error is True
    assert "SecretStr" not in (events[1].preview or "")


@pytest.mark.asyncio
async def test_kimi_global_log_source_classifies_auth_runtime_and_context_limit_errors(tmp_path: Path) -> None:
    log_file = tmp_path / "kimi-errors.log"
    log_file.write_text("bootstrap\n", encoding="utf-8")

    source = KimiGlobalLogSource(log_path=str(log_file))
    await source.initialize()

    log_file.write_text(
        "bootstrap\n"
        "2026-03-07 11:01:39.772 | ERROR    | kimi:run:10 - 401 Invalid Authentication\n"
        "2026-03-07 11:01:40.000 | ERROR    | kimi:run:11 - node:internal/modules/cjs/loader:1210\n"
        "2026-03-07 11:01:41.000 | ERROR    | kimi:run:12 - message exceeds context limit\n",
        encoding="utf-8",
    )

    events = await source.poll()

    assert len(events) == 3
    assert events[0].metrics.source == "kimi_global_auth_error"
    assert events[0].preview == "Erreur auth Kimi: authentification refusée"
    assert events[1].metrics.source == "kimi_global_runtime_error"
    assert events[1].preview == "Erreur runtime Kimi: Node.js"
    assert events[2].metrics.source == "kimi_global_context_limit_error"
    assert events[2].preview == "Erreur contexte Kimi: limite atteinte"


@pytest.mark.asyncio
async def test_kimi_global_log_source_classifies_request_json_error(tmp_path: Path) -> None:
    log_file = tmp_path / "kimi-bad-request.log"
    log_file.write_text("bootstrap\n", encoding="utf-8")

    source = KimiGlobalLogSource(log_path=str(log_file))
    await source.initialize()

    log_file.write_text(
        "bootstrap\n"
        "2026-03-07 19:08:00.000 | ERROR    | kimi:run:10 - Error code: 400 - Unterminated string starting at: line 1 column 60 (char 59)\n",
        encoding="utf-8",
    )

    events = await source.poll()

    assert len(events) == 1
    assert events[0].metrics.source == "kimi_global_request_error"
    assert events[0].preview == "Erreur requête Kimi: payload JSON invalide"


def test_format_log_error_message_avoids_false_context_limit_on_zero_tokens() -> None:
    auth_metrics = TokenMetrics(
        total_tokens=0,
        context_length=0,
        source="kimi_global_auth_error",
        is_api_error=True,
        raw_line="401 Invalid Authentication",
    )
    runtime_metrics = TokenMetrics(
        total_tokens=0,
        context_length=0,
        source="kimi_global_runtime_error",
        is_api_error=True,
        raw_line="node:internal/modules/cjs/loader:1210",
    )
    request_metrics = TokenMetrics(
        total_tokens=0,
        context_length=0,
        source="kimi_global_request_error",
        is_api_error=True,
        raw_line="Error code: 400 - Unterminated string",
    )
    context_metrics = TokenMetrics(
        total_tokens=0,
        context_length=0,
        source="kimi_global_context_limit_error",
        is_api_error=True,
        raw_line="message exceeds context limit",
    )

    assert _format_log_error_message("kimi_global_auth_error", auth_metrics) == (
        "⚠️ [API ERROR] Authentification Kimi refusée"
    )
    assert _format_log_error_message("kimi_global_runtime_error", runtime_metrics) == (
        "⚠️ [API ERROR] Erreur runtime Kimi détectée"
    )
    assert _format_log_error_message("kimi_global_request_error", request_metrics) == (
        "⚠️ [API ERROR] Requête Kimi invalide détectée"
    )
    assert _format_log_error_message("kimi_global_context_limit_error", context_metrics) == (
        "⚠️ [API ERROR] Tokens: inconnus (limite de contexte atteinte)"
    )


def test_should_emit_error_log_deduplicates_identical_messages_during_cooldown() -> None:
    cache: dict[str, float] = {}
    message = "⚠️ [API ERROR] Erreur runtime Kimi détectée"

    assert _should_emit_error_log(cache, message, now_ts=10.0, cooldown_seconds=2.0) is True
    assert _should_emit_error_log(cache, message, now_ts=11.0, cooldown_seconds=2.0) is False
    assert _should_emit_error_log(cache, message, now_ts=12.1, cooldown_seconds=2.0) is True


@pytest.mark.asyncio
async def test_kimi_session_source_reads_incremental_context_and_optional_metadata(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    root_dir = sessions_root / "workspace-a"
    session_dir = root_dir / "session-123"
    session_dir.mkdir(parents=True)

    metadata_file = session_dir / "metadata.json"
    metadata_file.write_text(
        json.dumps({"session_id": "external-123", "title": "Untitled", "archived": False}),
        encoding="utf-8",
    )

    context_file = session_dir / "context.jsonl"
    context_file.write_text(
        "{\"role\": \"_checkpoint\", \"id\": 0}\n"
        "{\"role\": \"user\", \"content\": \"Bonjour Kimi\"}\n",
        encoding="utf-8",
    )

    source = KimiSessionSource(
        sessions_path=str(sessions_root),
        max_sessions_per_poll=10,
        discovery_batch_size=10,
        initial_tail_bytes=4096,
    )
    await source.initialize()

    initial_events = await source.poll()

    assert len(initial_events) == 2
    assert initial_events[0].metrics.source == "kimi_session_checkpoint"
    assert initial_events[0].session_external_id == "external-123"
    assert initial_events[1].metrics.source == "kimi_session_user"
    assert initial_events[1].preview == "Bonjour Kimi"

    with context_file.open("a", encoding="utf-8") as file_handle:
        file_handle.write('{"role": "_usage", "token_count": 6853}\n')
        file_handle.write(
            '{"role": "assistant", "content": [{"type": "text", "text": "Réponse avec outil"}], '
            '"tool_calls": [{"id": "call-1", "type": "function"}]}\n'
        )

    incremental_events = await source.poll()

    assert len(incremental_events) == 2
    assert incremental_events[0].metrics.source == "kimi_session_usage"
    assert incremental_events[0].metrics.total_tokens == 6853
    assert incremental_events[1].metrics.source == "kimi_session_assistant"
    assert "outils: 1" in (incremental_events[1].preview or "")

    new_session_dir = root_dir / "session-without-metadata"
    new_session_dir.mkdir(parents=True)
    (new_session_dir / "context.jsonl").write_text(
        '{"role": "tool", "content": "Commande exécutée", "tool_call_id": "functions.WriteFile:0"}\n',
        encoding="utf-8",
    )

    fallback_events = await source.poll()

    assert len(fallback_events) == 1
    assert fallback_events[0].metrics.source == "kimi_session_tool"
    assert fallback_events[0].session_external_id == "session-without-metadata"
    assert "functions.WriteFile:0" in (fallback_events[0].preview or "")


@pytest.mark.asyncio
async def test_kimi_session_source_ignores_invalid_json_and_falls_back_when_metadata_is_invalid(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_dir = sessions_root / "workspace-b" / "session-invalid"
    session_dir.mkdir(parents=True)

    (session_dir / "metadata.json").write_text("{invalid-json", encoding="utf-8")
    (session_dir / "context.jsonl").write_text(
        "not-json\n"
        '{"role": "user", "content": "Message conservé"}\n'
        '{"role": "_usage", "token_count": "42"}\n',
        encoding="utf-8",
    )

    source = KimiSessionSource(
        sessions_path=str(sessions_root),
        max_sessions_per_poll=10,
        discovery_batch_size=10,
        initial_tail_bytes=4096,
    )
    await source.initialize()

    events = await source.poll()

    assert len(events) == 2
    assert events[0].metrics.source == "kimi_session_user"
    assert events[0].session_external_id == "session-invalid"
    assert events[1].metrics.source == "kimi_session_usage"
    assert events[1].metrics.total_tokens == 42