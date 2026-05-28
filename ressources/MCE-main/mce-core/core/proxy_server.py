"""
MCE — Proxy Server
FastAPI-based JSON-RPC reverse proxy. Orchestrates the full MCE pipeline:

  Cache Check → Forward to MCP → Economist Evaluation →
  Squeeze Engine → Policy Engine → Intelligence Layer → Return Minified Response
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from core.context_manager import ContextManager
from core.mcp_client import MCPClient
from engine.circuit_breaker import CircuitBreaker
from engine.lazy_registrar import LazyRegistrar
from engine.policy_engine import PolicyEngine, PolicyDecision
from engine.guardian.permission_gate import PermissionGate, GateDecision
from engine.skills.skill_loader import SkillLoader
from engine.squeeze.layer1_pruner import Layer1Pruner
from engine.squeeze.layer2_semantic import Layer2SemanticRouter
from engine.squeeze.layer3_synthesizer import Layer3Synthesizer
from engine.token_economist import TokenEconomist, Action
from models.semantic_cache import SemanticCache
from schemas.json_rpc import JsonRpcRequest, JsonRpcResponse, JsonRpcError
from schemas.mce_config import MCEConfig
from utils.logger import get_logger, log_token_savings

_log = get_logger("Proxy")


# ──────────────────────────────────────────────
# Proxy Server
# ──────────────────────────────────────────────

class ProxyServer:
    """
    The MCE reverse proxy.

    Exposes a single POST endpoint that accepts JSON-RPC requests,
    runs them through the full MCE pipeline, and returns minified
    responses to the AI agent.
    """

    def __init__(self, config: MCEConfig):
        self.config = config

        # ── Core Components ───────────────────
        self.mcp_client = MCPClient(config.upstream_servers)
        self.economist = TokenEconomist(config.token_limits)
        self.policy = PolicyEngine(config.policy)
        self.breaker = CircuitBreaker(config.circuit_breaker)
        self.cache = SemanticCache(
            max_entries=config.cache.max_entries,
            ttl_seconds=config.cache.ttl_seconds,
        )
        self.registrar = LazyRegistrar()
        self.context = ContextManager()

        # Squeeze layers
        self.pruner = Layer1Pruner()
        self.semantic_router = (
            Layer2SemanticRouter(model_name=config.embeddings.model_name)
            if config.squeeze.layer2_semantic
            else None
        )
        self.synthesizer = (
            Layer3Synthesizer(config.synthesizer)
            if config.squeeze.layer3_synthesizer
            else None
        )

        # ── Intelligence Layer ────────────────
        self._session_ledger = None
        self._memvault = None
        self._time_machine = None
        self._drift_sentinel = None
        self._permission_gate = None
        self._skill_loader = None
        self._session_id: Optional[str] = None
        self._project_id: Optional[str] = None

        # ── Build app with lifespan ───────────
        self.app = FastAPI(
            title="MCE — Model Context Engine",
            description="Token-aware transparent proxy for MCP servers",
            version="1.0.0",
            lifespan=self._lifespan,
        )

        # ── Routes ────────────────────────────
        self._register_routes()

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Modern FastAPI lifespan handler (replaces deprecated on_event)."""
        # Startup
        await self.mcp_client.start()

        # Auto-discover tools from upstream servers
        await self._discover_upstream_tools()

        # Initialize intelligence layer
        await self._init_intelligence()

        # Warn if no upstream servers configured
        if not self.config.upstream_servers:
            _log.warning(
                "[mce.warning]No upstream MCP servers configured![/mce.warning] "
                "Add servers to config.yaml → upstream_servers"
            )

        _log.info(
            f"[mce.badge]\\[MCE][/mce.badge] "
            f"Proxy started on "
            f"[mce.info]{self.config.proxy.host}:{self.config.proxy.port}[/mce.info]"
        )

        yield

        # Shutdown — extract session learnings
        await self._shutdown_intelligence()

        await self.mcp_client.stop()
        _log.info("[mce.badge]\\[MCE][/mce.badge] Proxy shutting down")

    async def _init_intelligence(self) -> None:
        """Initialize the Meridian intelligence layer components."""
        from utils.project import get_project_id, get_session_id, ensure_storage_dirs

        self._project_id = get_project_id()
        self._session_id = get_session_id()

        storage_paths = ensure_storage_dirs(
            self._project_id,
            self._session_id,
            self.config.memvault.storage_path,
        )

        # SessionLedger (CostWatch)
        if self.config.cost_watch.enabled:
            try:
                from models.cost_store import CostStore
                from engine.intelligence.session_ledger import SessionLedger

                cost_store = CostStore(storage_paths["cost_db"])
                await cost_store.connect()

                self._session_ledger = SessionLedger(
                    config=self.config.cost_watch,
                    session_id=self._session_id,
                    store=cost_store,
                )
                _log.info(
                    "[mce.success]\\[CostWatch] Initialized[/mce.success] — "
                    f"Session budget: ${self.config.cost_watch.session_budget_usd:.2f}"
                )
            except Exception as exc:
                _log.warning(f"Failed to initialize SessionLedger: {exc}")

        # MemVault
        if self.config.memvault.enabled:
            try:
                from models.memory_store import MemoryStore
                from engine.intelligence.memvault import MemVault

                memory_store = MemoryStore(storage_paths["memory_db"])
                await memory_store.connect()

                self._memvault = MemVault(
                    config=self.config.memvault,
                    project_id=self._project_id,
                    session_id=self._session_id,
                    store=memory_store,
                )

                # Inject context from previous sessions
                context = await self._memvault.inject_context()
                mem_count = await self._memvault.get_memory_count()

                self.context.memory_summary = {
                    "memory_count": mem_count,
                    "project_id": self._project_id[:8],
                }

                if context:
                    _log.info(
                        f"[mce.success]\\[MemVault] Loaded {mem_count} memories[/mce.success]"
                    )
                else:
                    _log.info(
                        "[mce.badge]\\[MemVault][/mce.badge] Initialized — "
                        "no prior memories found"
                    )
            except Exception as exc:
                _log.warning(f"Failed to initialize MemVault: {exc}")

        # TimeMachine
        if self.config.time_machine.enabled:
            try:
                from engine.intelligence.time_machine import TimeMachine

                tm_db_path = storage_paths["session_dir"] / "timeline.db"
                self._time_machine = TimeMachine(
                    config=self.config.time_machine,
                    session_id=self._session_id,
                    db_path=tm_db_path,
                )
                await self._time_machine.connect()

                self.context.timeline_summary = self._time_machine.get_timeline_summary()
            except Exception as exc:
                _log.warning(f"Failed to initialize TimeMachine: {exc}")

        # DriftSentinel
        if self.config.drift_sentinel.enabled:
            try:
                from engine.guardian.drift_sentinel import DriftSentinel

                self._drift_sentinel = DriftSentinel(self.config.drift_sentinel)

                # Load constraints from MemVault if available
                if self._memvault is not None:
                    count = await self._drift_sentinel.load_constraints_from_memvault(
                        self._memvault
                    )

                self.context.guardian_summary = self._drift_sentinel.get_guardian_summary()
                _log.info(
                    f"[mce.success]\\[DriftSentinel] Initialized with "
                    f"{self._drift_sentinel.constraint_count} constraints[/mce.success]"
                )
            except Exception as exc:
                _log.warning(f"Failed to initialize DriftSentinel: {exc}")

        # PermissionGate
        try:
            from engine.guardian.permission_gate import PermissionGate

            self._permission_gate = PermissionGate(self.config.permission_profiles)
            _log.info(
                f"[mce.badge]\\[PermissionGate][/mce.badge] "
                f"Active profile: {self._permission_gate.active_profile_name}"
            )
        except Exception as exc:
            _log.warning(f"Failed to initialize PermissionGate: {exc}")

        # SkillForge
        if self.config.skills.enabled:
            try:
                self._skill_loader = SkillLoader(self.config.skills)
                self._skill_loader.load_skills(Path.cwd())
                self.context.skills_summary = self._skill_loader.get_skills_summary()
            except Exception as exc:
                _log.warning(f"Failed to initialize SkillForge: {exc}")

        # Update guardian summary once all sub-components are initialized
        self._update_guardian_summary()

    def _update_guardian_summary(self) -> None:
        """Merge guardian summaries from DriftSentinel and PermissionGate."""
        summary = {}
        if self._drift_sentinel is not None:
            summary.update(self._drift_sentinel.get_guardian_summary())
        if self._permission_gate is not None:
            summary.update(self._permission_gate.get_gate_summary())
        self.context.guardian_summary = summary

    async def _shutdown_intelligence(self) -> None:
        """Graceful shutdown: extract learnings, close DB connections."""
        # Extract session learnings
        if self._memvault is not None:
            try:
                memories = await self._memvault.extract_session_learnings()
                _log.info(
                    f"[mce.badge]\\[MemVault][/mce.badge] Session ended — "
                    f"extracted {len(memories)} memories"
                )
                await self._memvault.update_claude_md(Path.cwd())
            except Exception as exc:
                _log.warning(f"MemVault extraction/CLAUDE.md update failed: {exc}")

            try:
                await self._memvault._store.close()
            except Exception:
                pass

        # Close cost store
        # Close TimeMachine
        if self._time_machine is not None:
            try:
                await self._time_machine.close()
            except Exception:
                pass

        if self._session_ledger is not None:
            try:
                await self._session_ledger._store.close()
            except Exception:
                pass

    async def _discover_upstream_tools(self) -> None:
        """Auto-discover tools from upstream servers and register them."""
        for server in self.config.upstream_servers:
            try:
                schemas = await self.mcp_client.discover_tools(server.name)
                for schema in schemas:
                    self.registrar.register_tool(schema)
                    self.mcp_client.register_tool(schema.name, server.name)
                _log.info(
                    f"[mce.success]Discovered {len(schemas)} tools[/mce.success] "
                    f"from '{server.name}'"
                )
            except Exception as exc:
                _log.warning(
                    f"Failed to discover tools from '{server.name}': {exc}"
                )

    def _register_routes(self) -> None:
        """Register FastAPI routes."""

        @self.app.post("/")
        async def handle_jsonrpc(request: Request) -> Response:
            """Main JSON-RPC endpoint."""
            try:
                body = await request.json()
                rpc_request = JsonRpcRequest.model_validate(body)
            except Exception as exc:
                return JSONResponse(
                    content=JsonRpcResponse(
                        error=JsonRpcError(
                            code=-32700,
                            message=f"Parse error: {exc}",
                        )
                    ).model_dump(exclude_none=True),
                    status_code=200,
                )

            response = await self._process_request(rpc_request)
            if response is None:
                # JSON-RPC notification — no response body
                return Response(status_code=204)
            return JSONResponse(
                content=response.model_dump(exclude_none=True),
                status_code=200,
            )

        @self.app.get("/health")
        async def health() -> dict:
            """Health check endpoint."""
            return {
                "status": "ok",
                "engine": "MCE",
                "version": "1.0.0",
                "stats": self.context.summary(),
            }

        @self.app.get("/stats")
        async def stats() -> dict:
            """Session statistics endpoint."""
            return self.context.summary()

        @self.app.post("/profile/switch")
        async def switch_profile(request: Request) -> Response:
            """Dynamic profile switch endpoint."""
            try:
                body = await request.json()
                profile_name = body.get("profile", "")
                if self._permission_gate is not None:
                    success = self._permission_gate.switch_profile(profile_name)
                    if success:
                        # Update context summary
                        self._update_guardian_summary()
                        return JSONResponse(content={"status": "success", "profile": profile_name})
                return JSONResponse(
                    content={"status": "error", "message": "Failed to switch profile"},
                    status_code=400,
                )
            except Exception as exc:
                return JSONResponse(
                    content={"status": "error", "message": str(exc)},
                    status_code=500,
                )

    # ──────────────────────────────────────────
    # Main Pipeline
    # ──────────────────────────────────────────

    async def _process_request(self, request: JsonRpcRequest) -> JsonRpcResponse | None:
        """
        Execute the full MCE pipeline for a single JSON-RPC request.

        1.  MCP dual-mode normalization (tools/call)
        2.  Handle meta-tools (discover_capabilities, tools/list)
        3.  Check semantic cache
        4.  Check policy engine (pre-execution on arguments)
        5.  Forward to upstream MCP server
        6.  Record in circuit breaker (with error status)
        7.  Check policy engine (post-execution on response)
        8.  Evaluate token budget
        9.  Squeeze if over budget
        10. Cache the result
        11. Record context stats
        12. Fire intelligence layer (SessionLedger + MemVault)
        13. Return minified response (or None for notifications)
        """
        # ── MCP dual-mode: handle tools/call ──
        if request.method == "tools/call":
            tool_name = (request.params or {}).get("name", "")
            arguments = (request.params or {}).get("arguments", {})
        else:
            tool_name = request.method
            arguments = request.params or {}

        # JSON-RPC notifications (id=None) should not get a response
        is_notification = request.id is None
        call_start_time = time.monotonic()

        _log.info(f"[mce.badge]\\[MCE][/mce.badge] ← {tool_name}")

        # Helper to respect JSON-RPC notifications
        def _respond(result=None, error=None):
            if is_notification:
                return None
            return JsonRpcResponse(id=request.id, result=result, error=error)

        # 1a. Meta-tool: discover_capabilities
        if tool_name == "discover_capabilities":
            domain = arguments.get("domain", "")
            schemas = self.registrar.discover_capabilities(domain)
            return _respond(result=schemas)

        # 1b. Meta-tool: release_capabilities
        if tool_name == "release_capabilities":
            domain = arguments.get("domain", "")
            self.registrar.release_domain(domain)
            return _respond(result={"status": "success", "message": f"Released domain @{domain}"})

        # 1c. Meta-tool: search_tools
        if tool_name == "search_tools":
            query = arguments.get("query", "")
            top_k = int(arguments.get("top_k", 3))
            from models.embeddings import EmbeddingModel
            embedder = (
                self.semantic_router._embedder
                if self.semantic_router is not None
                else EmbeddingModel(self.config.embeddings.model_name)
            )
            schemas = self.registrar.search_tools(query, embedder, top_k)
            return _respond(result=schemas)

        # 1d. MCP standard: tools/list
        if tool_name == "tools/list":
            tools = self._build_tools_list()
            return _respond(result={"tools": tools})

        # Match SkillForge skills early (before cache check and execution)
        matched_skills = []
        skill_notices = []
        if self._skill_loader is not None:
            matched_skills = self._skill_loader.match_tool_call(tool_name, arguments)
            # If any matched skill requires a checkpoint, trigger it before execution
            if self._time_machine is not None and any(s.requires_checkpoint for s in matched_skills):
                skill_names = ", ".join(s.name for s in matched_skills if s.requires_checkpoint)
                await self._time_machine.checkpoint(
                    label=f"SkillForge trigger ({skill_names}) before {tool_name}"
                )
                self.context.timeline_summary = self._time_machine.get_timeline_summary()

            # Build skill notices
            for skill in matched_skills:
                notice_lines = [f"[MCE Skill: {skill.name} v{skill.version}]"]
                if skill.constraints:
                    notice_lines.append("  Constraints:")
                    for c in skill.constraints:
                        notice_lines.append(f"    - {c}")
                if skill.workflow:
                    notice_lines.append("  Workflow:")
                    for i, w in enumerate(skill.workflow, 1):
                        notice_lines.append(f"    {i}. {w}")
                skill_notices.append("\n".join(notice_lines))

        # 2. Semantic cache check
        if self.config.cache.enabled:
            cached = self.cache.get(tool_name, arguments)
            if cached is not None:
                self.context.record_request(
                    tool_name=tool_name,
                    raw_tokens=cached.token_count,
                    squeezed_tokens=cached.token_count,
                    was_cached=True,
                )
                return _respond(result=cached.payload)

        # 3. Permission Gate + Policy Engine (pre-execution check on arguments)
        policy_result = None
        if self._permission_gate is not None:
            gate_result = self._permission_gate.check(tool_name)
            if gate_result.decision == GateDecision.BLOCK:
                self.context.record_request(
                    tool_name=tool_name,
                    raw_tokens=0,
                    squeezed_tokens=0,
                    was_blocked=True,
                )
                self._update_guardian_summary()
                return _respond(
                    error=JsonRpcError(
                        code=-32001,
                        message=gate_result.reason,
                    )
                )
            elif gate_result.decision == GateDecision.AUTO_ALLOW:
                # Check for explicit PolicyEngine BLOCKS, but skip HITL prompts
                pe_result = self.policy.check(tool_name, arguments)
                if pe_result.decision == PolicyDecision.BLOCK:
                    policy_result = pe_result
                else:
                    policy_result = None
            else:  # GateDecision.PROMPT
                policy_result = self.policy.check(tool_name, arguments)
        else:
            policy_result = self.policy.check(tool_name, arguments)

        if policy_result is not None:
            if policy_result.decision == PolicyDecision.BLOCK:
                self.context.record_request(
                    tool_name=tool_name,
                    raw_tokens=0,
                    squeezed_tokens=0,
                    was_blocked=True,
                )
                return _respond(
                    error=JsonRpcError(
                        code=-32001,
                        message=policy_result.reason,
                    )
                )

            if policy_result.decision == PolicyDecision.HITL:
                approved = await self.policy.prompt_human(tool_name, policy_result)
                if not approved:
                    self.context.record_request(
                        tool_name=tool_name,
                        raw_tokens=0,
                        squeezed_tokens=0,
                        was_blocked=True,
                    )
                    return _respond(
                        error=JsonRpcError(
                            code=-32001,
                            message=f"[MCE HitL: Command not approved] {policy_result.reason}",
                        )
                    )

        # 4. Forward to upstream MCP server
        upstream_response = await self.mcp_client.call_tool(
            tool_name, arguments, request.id
        )

        # 5. Record in circuit breaker AFTER execution, with correct error status
        is_error = upstream_response.error is not None
        if not is_error and isinstance(upstream_response.result, dict):
            is_error = upstream_response.result.get("isError") is True

        breaker_state = self.breaker.record(tool_name, arguments, is_error=is_error)

        # Handle upstream errors
        if is_error:
            self.context.record_request(
                tool_name=tool_name, raw_tokens=0, squeezed_tokens=0
            )
            # If breaker tripped, return breaker alert instead of upstream error
            if breaker_state.is_tripped:
                self.context.record_request(
                    tool_name=tool_name,
                    raw_tokens=0,
                    squeezed_tokens=0,
                    breaker_tripped=True,
                )
                return _respond(
                    error=JsonRpcError(
                        code=-32002,
                        message=breaker_state.alert_message,
                    )
                )
            if is_notification:
                return None
            return upstream_response

        raw_result = upstream_response.result

        # 6. Policy engine (post-execution check on response payload)
        response_policy = self.policy.check(tool_name, raw_result)
        if response_policy.decision == PolicyDecision.BLOCK:
            self.context.record_request(
                tool_name=tool_name,
                raw_tokens=0,
                squeezed_tokens=0,
                was_blocked=True,
            )
            return _respond(
                error=JsonRpcError(
                    code=-32001,
                    message=response_policy.reason,
                )
            )

        # 7. Evaluate token budget
        report = self.economist.evaluate(raw_result)
        raw_tokens = report.token_count

        # 8. Squeeze if over budget
        notices = []
        if report.recommended_action == Action.SQUEEZE:
            squeezed_result, squeeze_notices = await self._squeeze(
                raw_result, tool_name, arguments
            )
            squeezed_tokens = self.economist.count_any(squeezed_result)
            log_token_savings(raw_tokens, squeezed_tokens)
            notices.extend(squeeze_notices)
        else:
            squeezed_result = raw_result
            squeezed_tokens = raw_tokens

        # 8b. Drift Sentinel check (post-execution constraint check)
        if self._drift_sentinel is not None:
            violation = await self._drift_sentinel.check_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                response=squeezed_result,
            )
            self._update_guardian_summary()
            if violation is not None and violation.blocked:
                self.context.record_request(
                    tool_name=tool_name,
                    raw_tokens=0,
                    squeezed_tokens=0,
                    was_blocked=True,
                )
                return _respond(
                    error=JsonRpcError(
                        code=-32001,
                        message=violation.violation_detail,
                    )
                )

        # 8c. Append notices (Squeeze + Skill)
        if skill_notices:
            notices.extend(skill_notices)

        if notices:
            if isinstance(squeezed_result, str):
                squeezed_result = squeezed_result + "\n\n" + "\n".join(notices)
            elif isinstance(squeezed_result, dict):
                existing = squeezed_result.get("_mce_notices", [])
                squeezed_result["_mce_notices"] = list(existing) + [n for n in notices if n not in existing]
            elif isinstance(squeezed_result, list):
                squeezed_result = {
                    "_mce_result": squeezed_result,
                    "_mce_notices": notices,
                }

        # 9. Cache the processed result
        if self.config.cache.enabled:
            # Check if this tool is a state-mutator
            state_mutators = {
                "write_file", "edit_file", "create_file", "replace_file_content",
                "multi_replace_file_content", "delete_file", "rm", "rmdir",
                "execute_command", "run_command", "shell_exec"
            }
            if tool_name in state_mutators:
                self.cache.clear()
                _log.info(f"[mce.badge]\\[Cache][/mce.badge] State mutation detected via {tool_name} — cache cleared")
            else:
                self.cache.put(tool_name, arguments, squeezed_result, squeezed_tokens)

        # 10. Record context stats
        self.context.record_request(
            tool_name=tool_name,
            raw_tokens=raw_tokens,
            squeezed_tokens=squeezed_tokens,
        )

        # 11. Fire intelligence layer (non-blocking)
        duration_ms = int((time.monotonic() - call_start_time) * 1000)
        tokens_saved = raw_tokens - squeezed_tokens

        asyncio.create_task(
            self._fire_intelligence(
                tool_name=tool_name,
                arguments=arguments,
                response=squeezed_result,
                raw_tokens=raw_tokens,
                squeezed_tokens=squeezed_tokens,
                tokens_saved=tokens_saved,
                duration_ms=duration_ms,
            )
        )

        if is_notification:
            return None
        return JsonRpcResponse(id=request.id, result=squeezed_result)

    # ──────────────────────────────────────────
    # Intelligence Layer (fire-and-forget)
    # ──────────────────────────────────────────

    async def _fire_intelligence(
        self,
        tool_name: str,
        arguments: dict,
        response: Any,
        raw_tokens: int,
        squeezed_tokens: int,
        tokens_saved: int,
        duration_ms: int,
    ) -> None:
        """
        Fire intelligence layer hooks asynchronously.
        This runs in the background and never blocks the response.
        """
        try:
            # SessionLedger: record cost
            if self._session_ledger is not None:
                alerts = await self._session_ledger.record_exchange(
                    tool_name=tool_name,
                    tokens_in=raw_tokens,
                    tokens_out=squeezed_tokens,
                    tokens_saved=tokens_saved,
                )
                # Update context manager with cost summary
                self.context.cost_summary = self._session_ledger.get_session_summary()

            # MemVault: observe tool call
            if self._memvault is not None:
                await self._memvault.observe(
                    tool_name=tool_name,
                    arguments=arguments,
                    response=response,
                    tokens_in=raw_tokens,
                    tokens_out=squeezed_tokens,
                    duration_ms=duration_ms,
                )
                # Update memory count
                mem_count = await self._memvault.get_memory_count()
                self.context.memory_summary = {
                    "memory_count": mem_count,
                    "project_id": self._project_id[:8] if self._project_id else "",
                }

            # TimeMachine: auto-checkpoint
            if self._time_machine is not None:
                is_file_write = tool_name in (
                    "write_file", "edit_file", "create_file",
                    "replace_file_content", "multi_replace_file_content",
                )
                is_destructive = tool_name in (
                    "execute_command", "run_command", "shell_exec",
                    "delete_file", "rm",
                )
                self._time_machine.record_tool_call(
                    tool_name=tool_name,
                    arguments=arguments,
                    tokens=raw_tokens + squeezed_tokens,
                    is_file_write=is_file_write,
                    is_destructive=is_destructive,
                )
                await self._time_machine.maybe_checkpoint(
                    tool_name=tool_name,
                    is_file_write=is_file_write,
                    is_destructive=is_destructive,
                )
                self.context.timeline_summary = self._time_machine.get_timeline_summary()

        except Exception as exc:
            _log.debug(f"Intelligence layer error (non-critical): {exc}")

    # ──────────────────────────────────────────
    # Squeeze Pipeline
    # ──────────────────────────────────────────

    async def _squeeze(
        self,
        payload: Any,
        tool_name: str,
        arguments: dict,
    ) -> tuple[Any, list[str]]:
        """Run the 3-layer Squeeze Engine on a payload. Returns (result, notices)."""
        result = payload
        all_notices: list[str] = []

        # Layer 1: Deterministic Pruner
        if self.config.squeeze.layer1_pruner:
            result = self.pruner.prune(result)
            all_notices.extend(self.pruner.notices)
            _log.debug(f"L1 Pruner done — {len(self.pruner.notices)} notices")

        # Re-check tokens after pruning
        post_prune_tokens = self.economist.count_any(result)
        if post_prune_tokens <= self.config.token_limits.safe_limit:
            return result, all_notices

        # Layer 2: Semantic Router
        if self.config.squeeze.layer2_semantic and self.semantic_router is not None:
            # Use the tool name + arguments as the "agent query"
            agent_query = f"{tool_name} {json.dumps(arguments, default=str)}"
            result = self.semantic_router.route(result, agent_query)

        # Re-check tokens after semantic routing
        post_semantic_tokens = self.economist.count_any(result)
        if post_semantic_tokens <= self.config.token_limits.safe_limit:
            return result, all_notices

        # Layer 3: Synthesizer (optional)
        if self.config.squeeze.layer3_synthesizer and self.synthesizer is not None:
            agent_query = f"{tool_name} {json.dumps(arguments, default=str)}"
            result = await self.synthesizer.synthesize(
                result if isinstance(result, str) else json.dumps(result, default=str),
                agent_query,
            )

        return result, all_notices

    # ──────────────────────────────────────────
    # tools/list
    # ──────────────────────────────────────────

    def _build_tools_list(self) -> list[dict]:
        """Build the tools/list response: meta-tools + all active tools."""
        tools = [
            self.registrar.get_meta_tool_schema(),
            self.registrar.get_release_tool_schema(),
            self.registrar.get_search_tool_schema(),
        ]

        # Include all currently-active tool schemas
        for name in self.registrar.active_tool_names:
            schema = self.registrar.get_active_schema(name)
            if schema:
                tools.append({
                    "name": schema.name,
                    "description": schema.description,
                    "inputSchema": schema.input_schema,
                })

        return tools
