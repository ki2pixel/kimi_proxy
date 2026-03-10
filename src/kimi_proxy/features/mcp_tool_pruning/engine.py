"""kimi_proxy.features.mcp_tool_pruning.engine

Moteur (couche Features, sans I/O) pour pruner *conditionnellement* les sorties des
outils MCP, en réécrivant uniquement certains champs string dans une réponse
JSON-RPC 2.0.

Invariants:
- Ne jamais modifier la structure JSON-RPC (jsonrpc, id, result/error).
- N'opérer que sur des strings (ex: result.content[*].text).
- Déclenchement strict sur request.method == "tools/call".
- Fail-open: sur toute erreur, retourner la réponse originale (ou un fallback
  heuristique configuré) sans casser le flux.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote, urlparse

from ...config.loader import MCPToolPruningConfig
from ..mcp_pruner.spec import PruneOptionsDict, SourceType

from .pruner_client import PruneTextResult
from .metrics import MCPToolPruningMetricsCollector


JsonObject = dict[str, object]
_DEFAULT_EXCLUDED_DIRS: tuple[str, ...] = (".agents", ".cline", ".clinerules", ".windsurf")
_PATH_LIKE_ARGUMENT_KEYS: frozenset[str] = frozenset(
    {
        "path",
        "file_path",
        "filepath",
        "paths",
        "directory",
        "dir",
        "cwd",
        "root",
        "roots",
        "uri",
        "uris",
    }
)


class PrunerCallable(Protocol):
    async def __call__(
        self,
        *,
        request_id: int,
        text: str,
        goal_hint: str,
        source_type: SourceType,
        options: PruneOptionsDict,
        call_timeout_ms: int,
    ) -> PruneTextResult | None: ...


@dataclass(frozen=True)
class MCPToolPruningResolvedConfig:
    enabled: bool
    min_chars: int
    call_timeout_ms: int
    max_chars_fallback: int
    goal_hint_override: str | None
    excluded_dirs: frozenset[str]
    options: PruneOptionsDict

    # Garde-fous locaux (anti over-design, mais protège contre des JSON énormes)
    max_depth: int = 20
    max_nodes: int = 20_000
    max_pruner_calls_per_response: int = 3


def resolve_mcp_tool_pruning_config(toml_cfg: MCPToolPruningConfig) -> MCPToolPruningResolvedConfig:
    """Résout la config runtime avec la règle ENV > TOML.

    Note: ce resolver ne lit *que* l'environnement et la structure TOML déjà chargée.
    """

    enabled = _env_bool("KIMI_MCP_TOOL_PRUNING_ENABLED", default=bool(toml_cfg.enabled))
    min_chars = _env_int("KIMI_MCP_TOOL_PRUNING_MIN_CHARS", default=int(toml_cfg.min_chars), min_value=0)
    call_timeout_ms = _env_int(
        "KIMI_MCP_TOOL_PRUNING_TIMEOUT_MS",
        default=int(toml_cfg.timeout_ms),
        min_value=1,
    )
    max_chars_fallback = _env_int(
        "KIMI_MCP_TOOL_PRUNING_MAX_CHARS_FALLBACK",
        default=int(toml_cfg.max_chars_fallback),
        min_value=0,
    )

    goal_hint_override_raw = os.getenv("KIMI_MCP_PRUNING_GOAL_HINT")
    goal_hint_override = goal_hint_override_raw.strip() if isinstance(goal_hint_override_raw, str) and goal_hint_override_raw.strip() else None
    excluded_dirs = _resolve_excluded_dirs(toml_cfg.excluded_dirs)

    # Options (env > toml)
    max_prune_ratio = _env_float(
        "KIMI_MCP_TOOL_PRUNING_MAX_PRUNE_RATIO",
        default=float(toml_cfg.options.max_prune_ratio),
        min_value=0.0,
        max_value=1.0,
    )
    min_keep_lines = _env_int(
        "KIMI_MCP_TOOL_PRUNING_MIN_KEEP_LINES",
        default=int(toml_cfg.options.min_keep_lines),
        min_value=0,
    )
    # On garde un comportement simple: `timeout_ms` des options suit par défaut le timeout d'appel.
    options_timeout_ms = call_timeout_ms
    annotate_lines = _env_bool(
        "KIMI_MCP_TOOL_PRUNING_ANNOTATE_LINES",
        default=bool(toml_cfg.options.annotate_lines),
    )
    include_markers = _env_bool(
        "KIMI_MCP_TOOL_PRUNING_INCLUDE_MARKERS",
        default=bool(toml_cfg.options.include_markers),
    )

    options: PruneOptionsDict = {
        "max_prune_ratio": max_prune_ratio,
        "min_keep_lines": min_keep_lines,
        "timeout_ms": options_timeout_ms,
        "annotate_lines": annotate_lines,
        "include_markers": include_markers,
    }

    return MCPToolPruningResolvedConfig(
        enabled=enabled,
        min_chars=min_chars,
        call_timeout_ms=call_timeout_ms,
        max_chars_fallback=max_chars_fallback,
        goal_hint_override=goal_hint_override,
        excluded_dirs=excluded_dirs,
        options=options,
    )


async def maybe_prune_jsonrpc_response(
    *,
    server_name: str,
    request_json: object,
    response_json: object,
    cfg: MCPToolPruningResolvedConfig,
    pruner: PrunerCallable,
    metrics: MCPToolPruningMetricsCollector | None = None,
) -> object:
    """Best-effort pruning sur une paire (requête tools/call, réponse).

    Fail-open: si structure inattendue ou erreur -> retourne response_json original.
    """

    started_perf = time.perf_counter()
    if metrics is not None:
        await metrics.record_call()

    if not cfg.enabled:
        if metrics is not None:
            await metrics.record_skip("disabled")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    if server_name == "pruner":
        if metrics is not None:
            await metrics.record_skip("server_pruner")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    if not isinstance(request_json, dict) or request_json.get("jsonrpc") != "2.0":
        if metrics is not None:
            await metrics.record_skip("invalid_request")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json
    if request_json.get("method") != "tools/call":
        if metrics is not None:
            await metrics.record_skip("non_tools_call")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    tool_name = _extract_tool_call_name(request_json)
    if tool_name in {"prune_text", "recover_text", "health"}:
        if metrics is not None:
            await metrics.record_skip("tool_excluded")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    if not isinstance(response_json, dict) or response_json.get("jsonrpc") != "2.0":
        if metrics is not None:
            await metrics.record_skip("invalid_response")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json
    if "error" in response_json:
        if metrics is not None:
            await metrics.record_skip("error_response")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json
    result_obj = response_json.get("result")
    if not isinstance(result_obj, dict):
        if metrics is not None:
            await metrics.record_skip("invalid_response")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    content_obj = result_obj.get("content")
    if not isinstance(content_obj, list) or not content_obj:
        if metrics is not None:
            await metrics.record_skip("no_content")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    request_paths = _extract_candidate_paths_from_arguments(
        _extract_tool_call_arguments(request_json),
        max_depth=cfg.max_depth,
        max_nodes=cfg.max_nodes,
    )
    if _contains_excluded_path(request_paths, cfg.excluded_dirs):
        if metrics is not None:
            await metrics.record_skip("excluded_path")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    if _response_content_contains_excluded_path(
        content_obj,
        excluded_dirs=cfg.excluded_dirs,
        max_depth=cfg.max_depth,
        max_nodes=cfg.max_nodes,
    ):
        if metrics is not None:
            await metrics.record_skip("excluded_path")
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    if metrics is not None:
        await metrics.record_eligible()

    goal_hint = cfg.goal_hint_override or _derive_goal_hint_from_tool_call(server_name, tool_name, request_json)
    source_type = _derive_source_type(server_name=server_name, tool_name=tool_name, request_json=request_json)

    remaining_calls = max(0, int(cfg.max_pruner_calls_per_response))
    node_budget = _NodeBudget(max_nodes=max(1, int(cfg.max_nodes)))
    call_seq = 0

    changed = False
    new_content: list[object] = []

    for item in content_obj:
        if not isinstance(item, dict):
            new_content.append(item)
            continue
        text_obj = item.get("text")
        if not isinstance(text_obj, str) or not text_obj:
            new_content.append(item)
            continue

        if metrics is not None:
            await metrics.record_text_examined(
                length_chars=len(text_obj),
                over_threshold=len(text_obj) >= max(0, int(cfg.min_chars)),
            )

        if len(text_obj) < max(0, int(cfg.min_chars)):
            new_content.append(item)
            continue

        call_seq += 1
        pruner_request_id = _child_request_id(request_json.get("id"), salt=17 + call_seq)

        used_fallback_mask = False

        try:
            new_text, remaining_calls = await _prune_text_maybe_json(
                original=text_obj,
                cfg=cfg,
                pruner=pruner,
                request_id=pruner_request_id,
                goal_hint=goal_hint,
                source_type=source_type,
                remaining_calls=remaining_calls,
                node_budget=node_budget,
                depth=0,
                metrics=metrics,
            )
        except Exception:
            # Fail-open strict.
            if metrics is not None:
                await metrics.record_fail_open()
            new_text = _fallback_or_original(text_obj, cfg)
            used_fallback_mask = new_text != text_obj

        if used_fallback_mask and metrics is not None:
            await metrics.record_fallback_mask()

        if new_text != text_obj:
            changed = True
            new_item: dict[str, object] = dict(item)
            new_item["text"] = new_text
            new_content.append(new_item)
        else:
            new_content.append(item)

        if metrics is not None:
            await metrics.record_text_after(length_chars=len(new_text), pruned=new_text != text_obj)

    if not changed:
        if metrics is not None:
            await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
        return response_json

    new_result: dict[str, object] = dict(result_obj)
    new_result["content"] = new_content

    new_response: dict[str, object] = dict(response_json)
    new_response["result"] = new_result

    if metrics is not None:
        await metrics.record_response_changed()
        await metrics.record_elapsed_ms(int((time.perf_counter() - started_perf) * 1000))
    return new_response


@dataclass
class _NodeBudget:
    max_nodes: int
    visited: int = 0

    def tick(self) -> bool:
        self.visited += 1
        return self.visited <= self.max_nodes


async def _prune_text_maybe_json(
    *,
    original: str,
    cfg: MCPToolPruningResolvedConfig,
    pruner: PrunerCallable,
    request_id: int,
    goal_hint: str,
    source_type: SourceType,
    remaining_calls: int,
    node_budget: _NodeBudget,
    depth: int,
    metrics: MCPToolPruningMetricsCollector | None,
) -> tuple[str, int]:
    if remaining_calls <= 0:
        return original, remaining_calls

    if _looks_like_json_string(original):
        try:
            parsed = json.loads(original)
        except Exception:
            # Traiter comme texte brut.
            return await _prune_plain_text(
                original=original,
                cfg=cfg,
                pruner=pruner,
                request_id=request_id,
                goal_hint=goal_hint,
                source_type=source_type,
                remaining_calls=remaining_calls,
                metrics=metrics,
            )

        if depth >= cfg.max_depth:
            return original, remaining_calls

        pruned_value, remaining_calls, changed = await _prune_json_value(
            value=parsed,
            cfg=cfg,
            pruner=pruner,
            request_id=request_id,
            goal_hint=goal_hint,
            source_type=source_type,
            remaining_calls=remaining_calls,
            node_budget=node_budget,
            depth=depth,
            metrics=metrics,
        )
        if not changed:
            return original, remaining_calls

        try:
            return json.dumps(pruned_value, ensure_ascii=False), remaining_calls
        except Exception:
            return original, remaining_calls

    return await _prune_plain_text(
        original=original,
        cfg=cfg,
        pruner=pruner,
        request_id=request_id,
        goal_hint=goal_hint,
        source_type=source_type,
        remaining_calls=remaining_calls,
        metrics=metrics,
    )


async def _prune_plain_text(
    *,
    original: str,
    cfg: MCPToolPruningResolvedConfig,
    pruner: PrunerCallable,
    request_id: int,
    goal_hint: str,
    source_type: SourceType,
    remaining_calls: int,
    metrics: MCPToolPruningMetricsCollector | None,
) -> tuple[str, int]:
    if remaining_calls <= 0:
        return original, remaining_calls

    remaining_calls_after_attempt = remaining_calls - 1

    ok = False
    had_exception = False
    try:
        result = await pruner(
            request_id=request_id,
            text=original,
            goal_hint=goal_hint,
            source_type=source_type,
            options=cfg.options,
            call_timeout_ms=cfg.call_timeout_ms,
        )
        ok = result is not None
    except Exception:
        had_exception = True
        ok = False
        if metrics is not None:
            await metrics.record_fail_open()
        if metrics is not None:
            await metrics.record_pruner_call(ok=False, had_exception=True)
        fallback = _fallback_or_original(original, cfg)
        if metrics is not None and fallback != original:
            await metrics.record_fallback_mask()
        return fallback, remaining_calls_after_attempt

    if metrics is not None:
        await metrics.record_pruner_call(ok=ok, had_exception=had_exception)

    if result is None:
        if metrics is not None:
            await metrics.record_fail_open()
        fallback = _fallback_or_original(original, cfg)
        if metrics is not None and fallback != original:
            await metrics.record_fallback_mask()
        return fallback, remaining_calls_after_attempt

    pruned_text = result.get("pruned_text")
    if isinstance(pruned_text, str) and pruned_text:
        return pruned_text, remaining_calls_after_attempt

    if metrics is not None:
        await metrics.record_fail_open()
    fallback = _fallback_or_original(original, cfg)
    if metrics is not None and fallback != original:
        await metrics.record_fallback_mask()
    return fallback, remaining_calls_after_attempt


async def _prune_json_value(
    *,
    value: object,
    cfg: MCPToolPruningResolvedConfig,
    pruner: PrunerCallable,
    request_id: int,
    goal_hint: str,
    source_type: SourceType,
    remaining_calls: int,
    node_budget: _NodeBudget,
    depth: int,
    metrics: MCPToolPruningMetricsCollector | None,
) -> tuple[object, int, bool]:
    if not node_budget.tick():
        return value, remaining_calls, False
    if depth >= cfg.max_depth:
        return value, remaining_calls, False

    if isinstance(value, str):
        if len(value) < max(0, int(cfg.min_chars)):
            return value, remaining_calls, False
        pruned, remaining_calls = await _prune_plain_text(
            original=value,
            cfg=cfg,
            pruner=pruner,
            request_id=request_id,
            goal_hint=goal_hint,
            source_type=source_type,
            remaining_calls=remaining_calls,
            metrics=metrics,
        )
        return pruned, remaining_calls, pruned != value

    if isinstance(value, list):
        changed = False
        out_list: list[object] = []
        for it in value:
            it2, remaining_calls, it_changed = await _prune_json_value(
                value=it,
                cfg=cfg,
                pruner=pruner,
                request_id=request_id,
                goal_hint=goal_hint,
                source_type=source_type,
                remaining_calls=remaining_calls,
                node_budget=node_budget,
                depth=depth + 1,
                metrics=metrics,
            )
            changed = changed or it_changed
            out_list.append(it2)
        return out_list, remaining_calls, changed

    if isinstance(value, dict):
        changed = False
        out_dict: dict[object, object] = {}
        for k, v in value.items():
            v2, remaining_calls, v_changed = await _prune_json_value(
                value=v,
                cfg=cfg,
                pruner=pruner,
                request_id=request_id,
                goal_hint=goal_hint,
                source_type=source_type,
                remaining_calls=remaining_calls,
                node_budget=node_budget,
                depth=depth + 1,
                metrics=metrics,
            )
            changed = changed or v_changed
            out_dict[k] = v2
        return out_dict, remaining_calls, changed

    return value, remaining_calls, False


def _extract_tool_call_name(request_json: JsonObject) -> str | None:
    params = request_json.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


def _extract_tool_call_arguments(request_json: JsonObject) -> object:
    params = request_json.get("params")
    if not isinstance(params, dict):
        return None
    return params.get("arguments")


def _derive_goal_hint_from_tool_call(server_name: str, tool_name: str | None, request_json: JsonObject) -> str:
    # Heuristique minimale et stable (pas d'I/O):
    # - inclure le serveur, le tool, et quelques arguments structurants.
    params = request_json.get("params")
    args_obj: object | None = None
    if isinstance(params, dict):
        arguments = params.get("arguments")
        if isinstance(arguments, dict):
            args_obj = arguments

    parts: list[str] = []
    parts.append(f"serveur={server_name}")
    if tool_name:
        parts.append(f"outil={tool_name}")

    if isinstance(args_obj, dict):
        for key in ("path", "pattern", "query", "glob", "filePattern"):
            v = args_obj.get(key)
            if isinstance(v, str) and v.strip():
                parts.append(f"{key}={v.strip()[:120]}")
    hint = " | ".join(parts)
    return hint if hint else "résultat d’outil MCP"


def _derive_source_type(*, server_name: str, tool_name: str | None, request_json: JsonObject) -> SourceType:
    # Best-effort: on conserve une logique simple.
    if server_name in {"ripgrep-agent", "fast-filesystem"}:
        return "code"
    if server_name in {"shrimp-task-manager", "sequential-thinking"}:
        return "docs"

    # Heuristique sur extension de fichier si présent.
    params = request_json.get("params")
    if isinstance(params, dict):
        args = params.get("arguments")
        if isinstance(args, dict):
            path_obj = args.get("path")
            if isinstance(path_obj, str):
                p = path_obj.lower()
                if p.endswith((".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".css", ".html", ".json", ".toml", ".yaml", ".yml")):
                    return "code"
                if p.endswith((".md", ".rst", ".txt")):
                    return "docs"

    return "logs"


def _fallback_or_original(original: str, cfg: MCPToolPruningResolvedConfig) -> str:
    if cfg.max_chars_fallback <= 0:
        return original
    if len(original) <= cfg.max_chars_fallback:
        return original
    return _fallback_mask(original, max_chars=cfg.max_chars_fallback)


def _fallback_mask(value: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return value
    if len(value) <= max_chars:
        return value

    head_chars = max(0, max_chars // 2)
    tail_chars = max(0, max_chars - head_chars)
    head = value[:head_chars]
    tail = value[-tail_chars:] if tail_chars > 0 else ""
    marker = f"\n... [KIMI_PROXY_MCP_TOOL_PRUNING_FALLBACK original_chars={len(value)}] ...\n"
    return f"{head}{marker}{tail}"


def _looks_like_json_string(value: str) -> bool:
    stripped = value.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _child_request_id(parent_id: object, *, salt: int) -> int:
    # JSON-RPC id peut être str|number|null. On génère un id int stable et sûr.
    if isinstance(parent_id, int) and not isinstance(parent_id, bool):
        return int(parent_id) + int(salt)
    # time_ns peut dépasser les 53 bits; on borne pour éviter surprises côté JSON.
    return int(time.time_ns() % (2**53))


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, *, default: int, min_value: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        v = int(raw.strip())
    except ValueError:
        return default
    if v < min_value:
        return min_value
    return v


def _env_float(name: str, *, default: float, min_value: float, max_value: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        v = float(raw.strip())
    except ValueError:
        return default
    if v < min_value:
        return min_value
    if v > max_value:
        return max_value
    return v


def _resolve_excluded_dirs(toml_dirs: tuple[str, ...]) -> frozenset[str]:
    env_raw = os.getenv("KIMI_MCP_TOOL_PRUNING_EXCLUDED_DIRS")
    if isinstance(env_raw, str):
        env_dirs = _parse_excluded_dirs_csv(env_raw)
        if env_dirs:
            return frozenset(env_dirs)

    toml_values = [item.strip() for item in toml_dirs if isinstance(item, str) and item.strip()]
    if toml_values:
        return frozenset(toml_values)

    return frozenset(_DEFAULT_EXCLUDED_DIRS)


def _parse_excluded_dirs_csv(value: str) -> tuple[str, ...]:
    seen: set[str] = set()
    parsed: list[str] = []
    for raw in value.split(","):
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        parsed.append(item)
    return tuple(parsed)


def _normalize_path_like(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""

    if normalized.startswith("file://"):
        try:
            parsed = urlparse(normalized)
            candidate = unquote(parsed.path or "")
            if parsed.netloc and not candidate.startswith("/"):
                candidate = f"/{candidate}"
            normalized = candidate or normalized
        except Exception:
            normalized = normalized

    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"/{2,}", "/", normalized)
    return normalized.strip()


def _split_path_segments(path: str) -> list[str]:
    normalized = _normalize_path_like(path)
    if not normalized:
        return []
    return [segment for segment in normalized.split("/") if segment and segment != "."]


def _looks_like_path(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith("file://"):
        return True
    if stripped.startswith(("/", "./", "../", ".\\", "..\\")):
        return True
    if "\\" in stripped or "/" in stripped:
        return True
    return bool(re.match(r"^[A-Za-z]:[/\\]", stripped))


def _is_excluded_path_recursive(path: str, excluded_dirs: frozenset[str]) -> bool:
    if not excluded_dirs:
        return False
    segments = _split_path_segments(path)
    return any(segment in excluded_dirs for segment in segments)


def _contains_excluded_path(paths: list[str], excluded_dirs: frozenset[str]) -> bool:
    return any(_is_excluded_path_recursive(path, excluded_dirs) for path in paths)


def _extract_candidate_paths_from_arguments(args: object, *, max_depth: int, max_nodes: int) -> list[str]:
    budget = _NodeBudget(max_nodes=max(1, max_nodes))
    collected: list[str] = []

    def _walk(value: object, *, active: bool, depth: int) -> None:
        if depth > max_depth or not budget.tick():
            return

        if isinstance(value, str):
            normalized = _normalize_path_like(value)
            if active and normalized:
                collected.append(normalized)
            return

        if isinstance(value, list):
            for item in value:
                _walk(item, active=active, depth=depth + 1)
            return

        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    continue
                key_active = active or key.strip().lower() in _PATH_LIKE_ARGUMENT_KEYS
                _walk(item, active=key_active, depth=depth + 1)

    _walk(args, active=False, depth=0)
    return collected


def _extract_candidate_paths_from_json(value: object, *, max_depth: int, max_nodes: int) -> list[str]:
    budget = _NodeBudget(max_nodes=max(1, max_nodes))
    collected: list[str] = []

    def _walk(current: object, *, depth: int) -> None:
        if depth > max_depth or not budget.tick():
            return

        if isinstance(current, str):
            normalized = _normalize_path_like(current)
            if normalized and _looks_like_path(normalized):
                collected.append(normalized)
            return

        if isinstance(current, list):
            for item in current:
                _walk(item, depth=depth + 1)
            return

        if isinstance(current, dict):
            for item in current.values():
                _walk(item, depth=depth + 1)

    _walk(value, depth=0)
    return collected


def _response_content_contains_excluded_path(
    content_obj: list[object],
    *,
    excluded_dirs: frozenset[str],
    max_depth: int,
    max_nodes: int,
) -> bool:
    for item in content_obj:
        if not isinstance(item, dict):
            continue
        text_obj = item.get("text")
        if not isinstance(text_obj, str) or not _looks_like_json_string(text_obj):
            continue
        try:
            parsed = json.loads(text_obj)
        except Exception:
            continue
        paths = _extract_candidate_paths_from_json(parsed, max_depth=max_depth, max_nodes=max_nodes)
        if _contains_excluded_path(paths, excluded_dirs):
            return True
    return False
