"""kimi_proxy.features.mcp_pruner.server

Serveur MCP Pruner (HTTP local) — JSON-RPC 2.0 sur `/rpc`.

Conforme à la spec A1:
- `docs/features/mcp-pruner.md`
- `src/kimi_proxy/features/mcp_pruner/spec.py` (types)

Objectif (Lot A2):
- Démarrer un serveur MCP **local-first** (aucun appel réseau externe)
- Exposer `tools/list` et `tools/call`
- Implémenter une baseline de pruning **heuristique** (pas de modèle ONNX/SWE-Pruner)
- Supporter `recover_text` via un store mémoire (TTL)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kimi_proxy.core.tokens import count_tokens_text

from kimi_proxy.config.loader import MCPPrunerBackendConfig, get_config, get_mcp_pruner_backend_config

from .deepinfra_client import (
    DEFAULT_DEEPINFRA_ENDPOINT_URL,
    DeepInfraClient,
    DeepInfraClientConfig,
    DeepInfraConfigError,
    DeepInfraError,
    DeepInfraHTTPError,
)
from .deepinfra_engine import prune_text_with_deepinfra


JsonDict = dict[str, object]
SourceType = Literal["code", "logs", "docs"]


DEFAULT_MCP_PROTOCOL_VERSION = "2025-11-25"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class MCPPrunerServerConfig:
    host: str = "0.0.0.0"
    port: int = 8006

    max_input_chars: int = 2_000_000
    prune_id_ttl_s: int = 600

    cache_ttl_s: int = 30
    cache_max_items: int = 256

    @classmethod
    def from_env(cls) -> "MCPPrunerServerConfig":
        host = os.getenv("MCP_PRUNER_HOST", "0.0.0.0").strip() or "0.0.0.0"

        def _env_int(name: str, default: int) -> int:
            raw = os.getenv(name)
            if raw is None:
                return default
            try:
                return int(raw.strip())
            except ValueError:
                return default

        return cls(
            host=host,
            port=_env_int("MCP_PRUNER_PORT", 8006),
            max_input_chars=_env_int("MCP_PRUNER_MAX_INPUT_CHARS", 2_000_000),
            prune_id_ttl_s=_env_int("MCP_PRUNER_PRUNE_ID_TTL_S", 600),
            cache_ttl_s=_env_int("MCP_PRUNER_CACHE_TTL_S", 30),
            cache_max_items=_env_int("MCP_PRUNER_CACHE_MAX_ITEMS", 256),
        )


@dataclass(frozen=True)
class _CachedPrune:
    created_at_s: float
    pruned_text: str
    annotations: list[JsonDict]
    stats: JsonDict
    warnings: list[str]


class PruneCache:
    """Cache TTL in-memory pour réduire les appels DeepInfra.

    Important: le contenu cache est stocké avec `prune_id=<pending>`; l'appelant
    remplace le prune_id au moment de la réponse.
    """

    def __init__(self, *, ttl_s: int, max_items: int) -> None:
        self._ttl_s = max(1, int(ttl_s))
        self._max_items = max(1, int(max_items))
        self._lock = asyncio.Lock()
        self._items: dict[str, _CachedPrune] = {}

    async def get(self, key: str) -> _CachedPrune | None:
        now = time.time()
        async with self._lock:
            self._gc_locked(now)
            item = self._items.get(key)
            if item is None:
                return None
            return item

    async def put(self, key: str, item: _CachedPrune) -> None:
        now = time.time()
        async with self._lock:
            self._items[key] = item
            self._gc_locked(now)

            # Trim best-effort si trop grand
            if len(self._items) > self._max_items:
                # supprimer les plus anciens
                oldest = sorted(self._items.items(), key=lambda kv: kv[1].created_at_s)
                for k, _ in oldest[: max(0, len(self._items) - self._max_items)]:
                    del self._items[k]

    def _gc_locked(self, now_s: float) -> None:
        expired: list[str] = []
        for key, item in self._items.items():
            if now_s - item.created_at_s > self._ttl_s:
                expired.append(key)
        for key in expired:
            del self._items[key]


class PrunerMetrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.calls_total = 0
        self.calls_deepinfra = 0
        self.fallbacks_deepinfra = 0
        self.cost_estimated_total_usd = 0.0

    async def record_call(self, *, backend: str, used_fallback: bool, cost_estimated_usd: float) -> None:
        async with self._lock:
            self.calls_total += 1
            if backend == "deepinfra":
                self.calls_deepinfra += 1
                if used_fallback:
                    self.fallbacks_deepinfra += 1
            self.cost_estimated_total_usd += float(cost_estimated_usd)

    async def snapshot(self) -> JsonDict:
        async with self._lock:
            fallback_rate = 0.0
            if self.calls_deepinfra > 0:
                fallback_rate = self.fallbacks_deepinfra / self.calls_deepinfra
            return {
                "calls_total": int(self.calls_total),
                "calls_deepinfra": int(self.calls_deepinfra),
                "fallbacks_deepinfra": int(self.fallbacks_deepinfra),
                "fallback_rate_deepinfra": round(float(fallback_rate), 6),
                "cost_estimated_total_usd": round(float(self.cost_estimated_total_usd), 8),
            }


@dataclass(frozen=True)
class _StoredPrune:
    created_at_s: float
    lines: list[str]


class PruneStore:
    """Store mémoire (TTL) pour `recover_text`.

    Notes:
    - On reste in-memory; pas de dépendance Core/DB.
    - Lock async pour rester cohérent en environnement ASGI.
    """

    def __init__(self, *, ttl_s: int) -> None:
        self._ttl_s = max(1, int(ttl_s))
        self._lock = asyncio.Lock()
        self._items: dict[str, _StoredPrune] = {}

    async def put(self, prune_id: str, *, lines: list[str]) -> None:
        now = time.time()
        async with self._lock:
            self._items[prune_id] = _StoredPrune(created_at_s=now, lines=lines)
            self._gc_locked(now)

    async def get(self, prune_id: str) -> list[str] | None:
        now = time.time()
        async with self._lock:
            self._gc_locked(now)
            item = self._items.get(prune_id)
            if item is None:
                return None
            return list(item.lines)

    def _gc_locked(self, now_s: float) -> None:
        expired: list[str] = []
        for key, item in self._items.items():
            if now_s - item.created_at_s > self._ttl_s:
                expired.append(key)
        for key in expired:
            del self._items[key]


def _jsonrpc_error(*, code: int, message: str, req_id: object | None, data: object | None = None) -> JsonDict:
    payload: JsonDict = {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": int(code), "message": message},
    }
    if data is not None:
        err = payload.get("error")
        if isinstance(err, dict):
            err["data"] = data
    return payload


def _jsonrpc_result(*, req_id: object | None, result: object) -> JsonDict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_tool_result(*, req_id: object | None, tool_payload: object) -> JsonDict:
    return _jsonrpc_result(
        req_id=req_id,
        result={
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(tool_payload, ensure_ascii=False),
                }
            ]
        },
    )


def _extract_request_id(obj: object) -> object | None:
    if isinstance(obj, dict) and "id" in obj:
        return obj.get("id")
    return None


def _safe_get_dict(obj: object, key: str) -> dict[str, object] | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, dict):
        return value
    return None


def _safe_get_str(obj: object, key: str) -> str | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, str):
        return value
    return None


def _safe_get_bool(obj: object, key: str) -> bool | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, bool):
        return value
    return None


def _safe_get_int(obj: object, key: str) -> int | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _safe_get_float(obj: object, key: str) -> float | None:
    if not isinstance(obj, dict):
        return None
    value = obj.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _parse_goal_keywords(goal_hint: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9_]{4,}", goal_hint.lower())
    dedup: list[str] = []
    for t in tokens:
        if t not in dedup:
            dedup.append(t)
        if len(dedup) >= 8:
            break
    return dedup


def _baseline_prune(
    *,
    text: str,
    goal_hint: str,
    source_type: SourceType,
    max_prune_ratio: float,
    min_keep_lines: int,
    annotate_lines: bool,
    include_markers: bool,
) -> tuple[str, list[JsonDict], JsonDict]:
    lines = text.splitlines()
    if not lines:
        stats: JsonDict = {
            "original_lines": 0,
            "kept_lines": 0,
            "pruned_lines": 0,
            "pruned_ratio": 0.0,
            "tokens_est_before": 0,
            "tokens_est_after": 0,
            "elapsed_ms": 0,
            "used_fallback": False,
        }
        return "", [], stats

    keywords = _parse_goal_keywords(goal_hint)
    structural_re = re.compile(r"^(\s*(def|class)\s+|\s*import\s+|\s*from\s+.+\s+import\s+)")

    keep: set[int] = set()

    head = min(30, len(lines))
    tail = min(30, len(lines))
    for i in range(head):
        keep.add(i)
    for i in range(max(0, len(lines) - tail), len(lines)):
        keep.add(i)

    for idx, line in enumerate(lines):
        if structural_re.match(line):
            keep.add(idx)
            continue

        low = line.lower()
        if any(k in low for k in keywords):
            keep.add(idx)
            continue

        if source_type == "logs":
            if "error" in low or "exception" in low or "traceback" in low:
                keep.add(idx)
                continue

    # Invariants anti sur-pruning
    min_keep_lines_n = max(0, int(min_keep_lines))
    if len(keep) < min_keep_lines_n:
        for i in range(len(lines)):
            keep.add(i)
            if len(keep) >= min_keep_lines_n:
                break

    max_prune_ratio_n = max(0.0, min(1.0, float(max_prune_ratio)))
    min_keep_by_ratio = int(len(lines) * (1.0 - max_prune_ratio_n))
    if len(keep) < min_keep_by_ratio:
        for i in range(len(lines)):
            keep.add(i)
            if len(keep) >= min_keep_by_ratio:
                break

    kept_sorted = sorted(keep)

    annotations: list[JsonDict] = []
    out_lines: list[str] = []

    def _emit_line(original_idx: int) -> None:
        content = lines[original_idx]
        if annotate_lines:
            out_lines.append(f"{original_idx + 1}│ {content}")
        else:
            out_lines.append(content)

    def _emit_pruned_block(start_idx: int, end_idx: int) -> None:
        pruned_count = end_idx - start_idx + 1
        reason = "hors focus"
        if keywords:
            reason = f"hors focus: {keywords[0]}"

        marker = f"⟦PRUNÉ: prune_id=<pending> lignes {start_idx + 1}-{end_idx + 1} ({pruned_count}) raison={reason}⟧"
        annotations.append(
            {
                "kind": "pruned_block",
                "original_start_line": start_idx + 1,
                "original_end_line": end_idx + 1,
                "pruned_line_count": pruned_count,
                "reason": reason,
                "marker": marker,
            }
        )
        if include_markers:
            out_lines.append(marker)

    last_kept = -1
    for k in kept_sorted:
        if k > last_kept + 1:
            _emit_pruned_block(last_kept + 1, k - 1)
        _emit_line(k)
        last_kept = k

    if last_kept < len(lines) - 1:
        _emit_pruned_block(last_kept + 1, len(lines) - 1)

    pruned_text = "\n".join(out_lines)

    original_lines = len(lines)
    pruned_lines = original_lines - len(keep)
    pruned_ratio = pruned_lines / original_lines if original_lines > 0 else 0.0

    stats: JsonDict = {
        "original_lines": original_lines,
        "kept_lines": len(keep),
        "pruned_lines": pruned_lines,
        "pruned_ratio": round(pruned_ratio, 6),
        "tokens_est_before": count_tokens_text(text),
        "tokens_est_after": count_tokens_text(pruned_text),
        "elapsed_ms": 0,
        "used_fallback": False,
    }
    return pruned_text, annotations, stats


async def _health_payload(*, metrics: PrunerMetrics) -> JsonDict:
    base: JsonDict = {
        "status": "healthy",
        "server": "mcp-pruner",
        "version": "0.1.0",
        "capabilities": ["prune_text", "recover_text", "annotations", "markers"],
        "timestamp": _now_iso(),
    }
    base["metrics"] = await metrics.snapshot()
    return base


def create_app(*, config: MCPPrunerServerConfig | None = None) -> FastAPI:
    cfg = config or MCPPrunerServerConfig.from_env()
    store = PruneStore(ttl_s=cfg.prune_id_ttl_s)
    metrics = PrunerMetrics()

    # Fallback TOML pour la sélection backend et certains paramètres.
    # La priorité finale reste: env > toml.
    try:
        toml_mcp_pruner_cfg: MCPPrunerBackendConfig = get_mcp_pruner_backend_config(get_config())
    except Exception:
        # Fail-open: si config.toml est indisponible, on retombe sur les defaults.
        toml_mcp_pruner_cfg = MCPPrunerBackendConfig()

    cache_ttl_s = cfg.cache_ttl_s
    if os.getenv("MCP_PRUNER_CACHE_TTL_S") is None:
        cache_ttl_s = int(toml_mcp_pruner_cfg.cache_ttl_s)

    cache_max_items = cfg.cache_max_items
    if os.getenv("MCP_PRUNER_CACHE_MAX_ITEMS") is None and os.getenv("MCP_PRUNER_CACHE_MAX_ENTRIES") is None:
        cache_max_items = int(toml_mcp_pruner_cfg.cache_max_entries)

    cache = PruneCache(ttl_s=cache_ttl_s, max_items=cache_max_items)

    deepinfra_http_client: httpx.AsyncClient | None = None

    app = FastAPI()

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal deepinfra_http_client
        # Client partagé (keep-alive) pour DeepInfra.
        deepinfra_http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        nonlocal deepinfra_http_client
        if deepinfra_http_client is not None:
            await deepinfra_http_client.aclose()
            deepinfra_http_client = None

    tools_list: list[JsonDict] = [
        {
            "name": "prune_text",
            "description": "Élague un texte (baseline heuristique) avec annotations + markers.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "goal_hint": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["code", "logs", "docs"]},
                    "options": {
                        "type": "object",
                        "properties": {
                            "max_prune_ratio": {"type": "number", "minimum": 0, "maximum": 1},
                            "min_keep_lines": {"type": "integer", "minimum": 0},
                            "timeout_ms": {"type": "integer", "minimum": 1},
                            "annotate_lines": {"type": "boolean"},
                            "include_markers": {"type": "boolean"},
                        },
                        "required": [
                            "max_prune_ratio",
                            "min_keep_lines",
                            "timeout_ms",
                            "annotate_lines",
                            "include_markers",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["text", "goal_hint", "source_type", "options"],
                "additionalProperties": False,
            },
        },
        {
            "name": "recover_text",
            "description": "Récupère des plages de lignes brutes pour un prune_id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prune_id": {"type": "string"},
                    "ranges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_line": {"type": "integer", "minimum": 1},
                                "end_line": {"type": "integer", "minimum": 1},
                            },
                            "required": ["start_line", "end_line"],
                            "additionalProperties": False,
                        },
                    },
                    "include_line_numbers": {"type": "boolean"},
                },
                "required": ["prune_id", "ranges", "include_line_numbers"],
                "additionalProperties": False,
            },
        },
        {
            "name": "health",
            "description": "Retourne l'état de santé du serveur.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]

    @app.get("/health")
    async def get_health() -> JSONResponse:
        return JSONResponse(content=await _health_payload(metrics=metrics))

    @app.post("/rpc")
    async def rpc(request: Request) -> JSONResponse:
        try:
            req_obj: object = await request.json()
        except Exception:
            return JSONResponse(content=_jsonrpc_error(code=-32700, message="Parse error", req_id=None))

        req_id = _extract_request_id(req_obj)
        if not isinstance(req_obj, dict) or req_obj.get("jsonrpc") != "2.0" or not isinstance(req_obj.get("method"), str):
            return JSONResponse(content=_jsonrpc_error(code=-32600, message="Invalid Request", req_id=req_id))

        method = str(req_obj.get("method"))
        params = req_obj.get("params")
        params_dict = params if isinstance(params, dict) else {}

        # Handshake
        if method == "initialize":
            protocol_version = DEFAULT_MCP_PROTOCOL_VERSION
            if isinstance(params_dict.get("protocolVersion"), str):
                protocol_version = str(params_dict.get("protocolVersion"))
            return JSONResponse(
                content=_jsonrpc_result(
                    req_id=req_id,
                    result={
                        "protocolVersion": protocol_version,
                        "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                        "serverInfo": {"name": "mcp-pruner", "version": "0.1.0"},
                    },
                )
            )

        if method == "notifications/initialized":
            return JSONResponse(content=_jsonrpc_result(req_id=req_id, result={"ok": True}))

        if method == "tools/list":
            return JSONResponse(content=_jsonrpc_result(req_id=req_id, result={"tools": tools_list}))

        if method == "tools/call":
            tool_name = _safe_get_str(params_dict, "name")
            tool_args = _safe_get_dict(params_dict, "arguments") or {}
            if tool_name is None:
                return JSONResponse(
                    content=_jsonrpc_error(code=-32602, message="Invalid params: missing tool name", req_id=req_id)
                )

            if tool_name == "prune_text":
                return JSONResponse(
                    content=await _tool_prune_text(
                        cfg=cfg,
                        store=store,
                        cache=cache,
                        metrics=metrics,
                        deepinfra_http_client=deepinfra_http_client,
                        toml_backend_cfg=toml_mcp_pruner_cfg,
                        req_id=req_id,
                        args=tool_args,
                    )
                )
            if tool_name in {"recover_text", "recover_range"}:
                return JSONResponse(content=await _tool_recover_text(store=store, req_id=req_id, args=tool_args))
            if tool_name == "health":
                return JSONResponse(
                    content=_jsonrpc_tool_result(req_id=req_id, tool_payload=await _health_payload(metrics=metrics))
                )

            return JSONResponse(
                content=_jsonrpc_error(code=-32602, message=f"Invalid params: unknown tool '{tool_name}'", req_id=req_id)
            )

        # Optional discovery APIs
        if method in {"resources/list", "resources/templates/list", "prompts/list"}:
            key = "resources"
            if method == "resources/templates/list":
                key = "resourceTemplates"
            if method == "prompts/list":
                key = "prompts"
            return JSONResponse(content=_jsonrpc_result(req_id=req_id, result={key: []}))

        # Legacy direct methods
        if method == "health":
            return JSONResponse(content=_jsonrpc_result(req_id=req_id, result=await _health_payload(metrics=metrics)))
        if method == "prune_text":
            if not isinstance(params, dict):
                return JSONResponse(content=_jsonrpc_error(code=-32602, message="Invalid params", req_id=req_id))
            return JSONResponse(
                content=await _tool_prune_text(
                    cfg=cfg,
                    store=store,
                    cache=cache,
                    metrics=metrics,
                    deepinfra_http_client=deepinfra_http_client,
                    toml_backend_cfg=toml_mcp_pruner_cfg,
                    req_id=req_id,
                    args=params,
                )
            )
        if method in {"recover_text", "recover_range"}:
            if not isinstance(params, dict):
                return JSONResponse(content=_jsonrpc_error(code=-32602, message="Invalid params", req_id=req_id))
            return JSONResponse(content=await _tool_recover_text(store=store, req_id=req_id, args=params))

        return JSONResponse(content=_jsonrpc_error(code=-32601, message=f"Method not found: {method}", req_id=req_id))

    return app


async def _tool_prune_text(
    *,
    cfg: MCPPrunerServerConfig,
    store: PruneStore,
    cache: PruneCache,
    metrics: PrunerMetrics,
    deepinfra_http_client: httpx.AsyncClient | None,
    toml_backend_cfg: MCPPrunerBackendConfig,
    req_id: object | None,
    args: dict[str, object],
) -> JsonDict:
    text = _safe_get_str(args, "text")
    goal_hint = _safe_get_str(args, "goal_hint")
    source_type_raw = _safe_get_str(args, "source_type")
    options = _safe_get_dict(args, "options")

    if text is None or goal_hint is None or source_type_raw is None or options is None:
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: expected {text, goal_hint, source_type, options}",
            req_id=req_id,
        )

    if source_type_raw not in {"code", "logs", "docs"}:
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: source_type must be one of code|logs|docs",
            req_id=req_id,
        )

    prune_id = f"prn_{uuid.uuid4().hex}"
    backend = _get_pruning_backend_from_env(toml_backend_cfg)
    _ = time.time()  # wall clock placeholder (utile si on ajoute des timestamps plus tard)
    started_perf = time.perf_counter()

    if len(text) > cfg.max_input_chars:
        # Fail-open: no-op + warning
        await store.put(prune_id, lines=text.splitlines())
        payload = {
            "prune_id": prune_id,
            "pruned_text": text,
            "annotations": [],
            "stats": {
                "backend": backend,
                "original_lines": len(text.splitlines()),
                "kept_lines": len(text.splitlines()),
                "pruned_lines": 0,
                "pruned_ratio": 0.0,
                "tokens_est_before": count_tokens_text(text),
                "tokens_est_after": count_tokens_text(text),
                "elapsed_ms": 0,
                "used_fallback": True,
            },
            "warnings": ["input_too_large"],
        }
        tokens_saved_est, cost_estimated_usd = _compute_savings(payload["stats"])  # type: ignore[arg-type]
        stats_obj = payload.get("stats")
        if isinstance(stats_obj, dict):
            stats_obj["tokens_saved_est"] = tokens_saved_est
            stats_obj["cost_estimated_usd"] = cost_estimated_usd
            await metrics.record_call(backend=str(stats_obj.get("backend")), used_fallback=True, cost_estimated_usd=cost_estimated_usd)
        return _jsonrpc_tool_result(req_id=req_id, tool_payload=payload)

    max_prune_ratio = _safe_get_float(options, "max_prune_ratio")
    min_keep_lines = _safe_get_int(options, "min_keep_lines")
    timeout_ms = _safe_get_int(options, "timeout_ms")
    annotate_lines = _safe_get_bool(options, "annotate_lines")
    include_markers = _safe_get_bool(options, "include_markers")

    if (
        max_prune_ratio is None
        or min_keep_lines is None
        or timeout_ms is None
        or annotate_lines is None
        or include_markers is None
    ):
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: options must contain max_prune_ratio, min_keep_lines, timeout_ms, annotate_lines, include_markers",
            req_id=req_id,
        )

    if max_prune_ratio < 0.0 or max_prune_ratio > 1.0:
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: options.max_prune_ratio must be between 0 and 1",
            req_id=req_id,
        )

    if min_keep_lines < 0:
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: options.min_keep_lines must be >= 0",
            req_id=req_id,
        )

    if timeout_ms < 1:
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: options.timeout_ms must be >= 1",
            req_id=req_id,
        )

    # Timeout soft: baseline heuristique; on conserve le champ pour compat.
    _ = timeout_ms

    pruned_text: str
    annotations: list[JsonDict]
    stats: JsonDict
    warnings: list[str]

    if backend == "deepinfra":
        cache_key = _cache_key_for_prune(
            backend=backend,
            text=text,
            goal_hint=goal_hint,
            source_type=source_type_raw,
            options={
                "max_prune_ratio": max_prune_ratio,
                "min_keep_lines": min_keep_lines,
                "timeout_ms": timeout_ms,
                "annotate_lines": annotate_lines,
                "include_markers": include_markers,
            },
        )

        cached = await cache.get(cache_key)
        if cached is not None:
            pruned_text = str(cached.pruned_text)
            annotations = _clone_annotations(cached.annotations)
            stats = dict(cached.stats)
            warnings = list(cached.warnings) + ["cache_hit"]
            stats["deepinfra_latency_ms"] = 0
            stats["deepinfra_cached"] = True
        else:
            owned_client: httpx.AsyncClient | None = None
            http_client_to_use = deepinfra_http_client
            if http_client_to_use is None:
                owned_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
                http_client_to_use = owned_client
            try:
                deepinfra_cfg = _get_deepinfra_client_config(toml_backend_cfg)
                deepinfra_client = DeepInfraClient(deepinfra_cfg, http_client=http_client_to_use)

                out = await prune_text_with_deepinfra(
                    prune_id="<pending>",
                    text=text,
                    goal_hint=goal_hint,
                    source_type=source_type_raw,  # type: ignore[arg-type]
                    max_prune_ratio=max_prune_ratio,
                    min_keep_lines=min_keep_lines,
                    annotate_lines=annotate_lines,
                    include_markers=include_markers,
                    max_docs=deepinfra_cfg.max_docs,
                    deepinfra_client=deepinfra_client,
                )
                pruned_text = out.pruned_text
                annotations = out.annotations
                stats = dict(out.stats)
                warnings = list(out.warnings)

                # Cache best-effort
                await cache.put(
                    cache_key,
                    _CachedPrune(
                        created_at_s=time.time(),
                        pruned_text=pruned_text,
                        annotations=_clone_annotations(annotations),
                        stats=dict(stats),
                        warnings=list(warnings),
                    ),
                )
            except DeepInfraError as e:
                pruned_text, annotations, stats = _baseline_prune(
                    text=text,
                    goal_hint=goal_hint,
                    source_type=source_type_raw,  # type: ignore[arg-type]
                    max_prune_ratio=max_prune_ratio,
                    min_keep_lines=min_keep_lines,
                    annotate_lines=annotate_lines,
                    include_markers=include_markers,
                )
                stats["backend"] = "deepinfra"
                stats["used_fallback"] = True
                if isinstance(e, DeepInfraHTTPError):
                    status_obj = e.details.get("status_code") if isinstance(e.details, dict) else None
                    if isinstance(status_obj, int) and not isinstance(status_obj, bool):
                        stats["deepinfra_http_status"] = int(status_obj)
                warnings = ["deepinfra_error", str(e.code)]
            except Exception:
                pruned_text, annotations, stats = _baseline_prune(
                    text=text,
                    goal_hint=goal_hint,
                    source_type=source_type_raw,  # type: ignore[arg-type]
                    max_prune_ratio=max_prune_ratio,
                    min_keep_lines=min_keep_lines,
                    annotate_lines=annotate_lines,
                    include_markers=include_markers,
                )
                stats["backend"] = "deepinfra"
                stats["used_fallback"] = True
                warnings = ["deepinfra_error", "unknown"]
            finally:
                if owned_client is not None:
                    await owned_client.aclose()
    else:
        pruned_text, annotations, stats = _baseline_prune(
            text=text,
            goal_hint=goal_hint,
            source_type=source_type_raw,  # type: ignore[arg-type]
            max_prune_ratio=max_prune_ratio,
            min_keep_lines=min_keep_lines,
            annotate_lines=annotate_lines,
            include_markers=include_markers,
        )
        stats["backend"] = "heuristic"
        warnings = []

    # Remplacer le placeholder prune_id dans markers/annotations
    _replace_prune_id(annotations=annotations, prune_id=prune_id)
    pruned_text = pruned_text.replace("prune_id=<pending>", f"prune_id={prune_id}")

    elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
    stats["elapsed_ms"] = elapsed_ms

    tokens_saved_est, cost_estimated_usd = _compute_savings(stats)
    stats["tokens_saved_est"] = tokens_saved_est
    stats["cost_estimated_usd"] = cost_estimated_usd

    await store.put(prune_id, lines=text.splitlines())
    payload = {
        "prune_id": prune_id,
        "pruned_text": pruned_text,
        "annotations": annotations,
        "stats": stats,
        "warnings": warnings,
    }

    used_fallback = bool(stats.get("used_fallback")) if isinstance(stats.get("used_fallback"), bool) else False
    await metrics.record_call(backend=str(stats.get("backend")), used_fallback=used_fallback, cost_estimated_usd=cost_estimated_usd)
    return _jsonrpc_tool_result(req_id=req_id, tool_payload=payload)


def _get_pruning_backend_from_env(toml_cfg: MCPPrunerBackendConfig) -> Literal["heuristic", "deepinfra"]:
    raw = (os.getenv("KIMI_PRUNING_BACKEND") or "").strip().lower()
    if raw:
        if raw in {"deepinfra", "cloud"}:
            return "deepinfra"
        return "heuristic"
    return toml_cfg.backend


def _get_deepinfra_client_config(toml_cfg: MCPPrunerBackendConfig) -> DeepInfraClientConfig:
    """Construit la config DeepInfra avec priorité env > toml.

    Notes:
    - Les secrets restent en env (`DEEPINFRA_API_KEY`).
    - Les paramètres TOML servent de fallback si les env vars correspondantes sont absentes.
    """

    endpoint_url = (os.getenv("DEEPINFRA_ENDPOINT_URL") or "").strip() or DEFAULT_DEEPINFRA_ENDPOINT_URL
    api_key = (os.getenv("DEEPINFRA_API_KEY") or "").strip()
    if not api_key:
        raise DeepInfraConfigError("DEEPINFRA_API_KEY manquante", key="DEEPINFRA_API_KEY")

    def _env_int_optional(name: str) -> int | None:
        raw = os.getenv(name)
        if raw is None:
            return None
        if not raw.strip():
            return None
        try:
            return int(raw.strip())
        except ValueError:
            return None

    def _clamp_int(value: int, *, min_value: int, max_value: int) -> int:
        if value < min_value:
            return min_value
        if value > max_value:
            return max_value
        return value

    timeout_ms = _env_int_optional("DEEPINFRA_TIMEOUT_MS")
    if timeout_ms is None:
        timeout_ms = int(toml_cfg.deepinfra_timeout_ms)
    timeout_ms = _clamp_int(timeout_ms, min_value=1, max_value=120_000)

    max_docs = _env_int_optional("DEEPINFRA_MAX_DOCS")
    if max_docs is None:
        max_docs = int(toml_cfg.deepinfra_max_docs)
    max_docs = _clamp_int(max_docs, min_value=1, max_value=512)

    return DeepInfraClientConfig(endpoint_url=endpoint_url, api_key=api_key, timeout_ms=timeout_ms, max_docs=max_docs)


def _cache_key_for_prune(
    *,
    backend: str,
    text: str,
    goal_hint: str,
    source_type: str,
    options: dict[str, object],
) -> str:
    # Aucun contenu n'est loggé; on hash pour limiter la taille.
    blob = json.dumps(
        {
            "backend": backend,
            "source_type": source_type,
            "goal_hint": goal_hint,
            "options": options,
            "text": text,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _clone_annotations(annotations: list[JsonDict]) -> list[JsonDict]:
    cloned: list[JsonDict] = []
    for ann in annotations:
        if isinstance(ann, dict):
            cloned.append(dict(ann))
    return cloned


def _replace_prune_id(*, annotations: list[JsonDict], prune_id: str) -> None:
    # Remplacer dans annotations
    for ann in annotations:
        marker = ann.get("marker")
        if isinstance(marker, str):
            ann["marker"] = marker.replace("prune_id=<pending>", f"prune_id={prune_id}")


def _compute_savings(stats: JsonDict) -> tuple[int, float]:
    before = stats.get("tokens_est_before")
    after = stats.get("tokens_est_after")
    if not isinstance(before, int) or isinstance(before, bool):
        return 0, 0.0
    if not isinstance(after, int) or isinstance(after, bool):
        return 0, 0.0

    saved = max(0, int(before) - int(after))
    cost_per_1m = 0.01
    cost = (float(saved) * cost_per_1m) / 1_000_000.0
    return saved, round(cost, 8)


async def _tool_recover_text(
    *,
    store: PruneStore,
    req_id: object | None,
    args: dict[str, object],
) -> JsonDict:
    prune_id = _safe_get_str(args, "prune_id")
    ranges = args.get("ranges")
    include_line_numbers = _safe_get_bool(args, "include_line_numbers")

    if prune_id is None or not isinstance(ranges, list) or include_line_numbers is None:
        return _jsonrpc_error(
            code=-32602,
            message="Invalid params: expected {prune_id, ranges, include_line_numbers}",
            req_id=req_id,
        )

    stored_lines = await store.get(prune_id)
    if stored_lines is None:
        return _jsonrpc_error(
            code=-32004,
            message="prune_id_not_found",
            req_id=req_id,
            data={"code": "prune_id_not_found", "prune_id": prune_id},
        )

    chunks: list[str] = []
    for r in ranges:
        if not isinstance(r, dict):
            return _jsonrpc_error(code=-32602, message="Invalid params: range item must be object", req_id=req_id)
        start_line = _safe_get_int(r, "start_line")
        end_line = _safe_get_int(r, "end_line")
        if start_line is None or end_line is None or start_line < 1 or end_line < 1 or start_line > end_line:
            return _jsonrpc_error(
                code=-32005,
                message="invalid_range",
                req_id=req_id,
                data={"code": "invalid_range", "range": r},
            )

        if start_line > len(stored_lines):
            return _jsonrpc_error(
                code=-32005,
                message="invalid_range",
                req_id=req_id,
                data={"code": "invalid_range", "range": r, "max_line": len(stored_lines)},
            )

        start_idx = start_line - 1
        end_idx = min(end_line, len(stored_lines))
        for idx in range(start_idx, end_idx):
            line = stored_lines[idx]
            if include_line_numbers:
                chunks.append(f"{idx + 1}│ {line}")
            else:
                chunks.append(line)

    payload = {
        "raw_text": "\n".join(chunks),
        "metadata": {
            "prune_id": prune_id,
            "ranges": ranges,
            "line_numbering": "original",
        },
    }
    return _jsonrpc_tool_result(req_id=req_id, tool_payload=payload)


app = create_app()


def run() -> None:
    config = MCPPrunerServerConfig.from_env()

    # Import local pour éviter d'imposer uvicorn dans les chemins d'import des tests.
    import uvicorn

    uvicorn.run(
        "kimi_proxy.features.mcp_pruner.server:app",
        host=config.host,
        port=config.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    run()
