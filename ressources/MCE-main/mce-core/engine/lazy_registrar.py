"""
MCE — Lazy Registrar (Dynamic Tool Schema Management)
Just-in-Time schema injection: only load tool schemas when the agent
actually needs a specific domain, then remove them when done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from schemas.json_rpc import ToolSchema
from utils.logger import get_logger

_log = get_logger("Registrar")


# ──────────────────────────────────────────────
# Domain Catalog
# ──────────────────────────────────────────────

@dataclass
class DomainGroup:
    """A domain (e.g. @filesystem) and its associated tool schemas."""
    name: str
    tools: list[ToolSchema] = field(default_factory=list)
    is_active: bool = False


class LazyRegistrar:
    """
    Manages domain-grouped tool schemas.

    Instead of dumping all tool schemas into the system prompt upfront
    (the "token tax"), MCE exposes a single meta-tool `discover_capabilities(domain)`
    that temporarily injects schemas on demand.
    """

    def __init__(self):
        self._domains: dict[str, DomainGroup] = {}
        self._active_schemas: dict[str, ToolSchema] = {}  # tool_name → schema

    # ── Registration ──────────────────────────

    def register_tool(self, schema: ToolSchema) -> None:
        """Register a tool under its domain group."""
        domain = schema.domain
        if domain not in self._domains:
            self._domains[domain] = DomainGroup(name=domain)
        self._domains[domain].tools.append(schema)
        _log.debug(f"Registered tool '{schema.name}' in domain '@{domain}'")

    def register_tools(self, schemas: list[ToolSchema]) -> None:
        """Bulk register multiple tools."""
        for s in schemas:
            self.register_tool(s)

    # ── Discovery (the meta-tool) ─────────────

    def discover_capabilities(self, domain: str) -> list[dict[str, Any]]:
        """
        The meta-tool that agents call to discover available tools
        in a specific domain.

        Activates the domain and returns lightweight schema summaries.
        """
        group = self._domains.get(domain)
        if group is None:
            _log.warning(f"Domain '@{domain}' not found")
            return []

        group.is_active = True
        for tool in group.tools:
            self._active_schemas[tool.name] = tool

        _log.info(
            f"[mce.success]Activated[/mce.success] domain '@{domain}' "
            f"({len(group.tools)} tools)"
        )

        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in group.tools
        ]

    def release_domain(self, domain: str) -> None:
        """Deactivate a domain and remove its schemas from active context."""
        group = self._domains.get(domain)
        if group is None:
            return

        group.is_active = False
        for tool in group.tools:
            self._active_schemas.pop(tool.name, None)

        _log.info(f"Released domain '@{domain}'")

    # ── Lookup ────────────────────────────────

    def get_active_schema(self, tool_name: str) -> Optional[ToolSchema]:
        """Look up a currently-active tool schema by name."""
        return self._active_schemas.get(tool_name)

    def is_tool_active(self, tool_name: str) -> bool:
        """Check if a tool is currently injected into the active context."""
        return tool_name in self._active_schemas

    @property
    def active_tool_names(self) -> list[str]:
        return list(self._active_schemas.keys())

    @property
    def available_domains(self) -> list[str]:
        return list(self._domains.keys())

    @property
    def active_domains(self) -> list[str]:
        return [name for name, grp in self._domains.items() if grp.is_active]

    def get_meta_tool_schema(self) -> dict[str, Any]:
        """Return the schema for the `discover_capabilities` meta-tool itself."""
        return {
            "name": "discover_capabilities",
            "description": (
                "Discover available tool capabilities in a specific domain. "
                f"Available domains: {', '.join(self.available_domains) or 'none registered'}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "The domain to discover (e.g. 'filesystem', 'database')",
                    }
                },
                "required": ["domain"],
            },
        }

    def get_release_tool_schema(self) -> dict[str, Any]:
        """Return the schema for the `release_capabilities` meta-tool."""
        return {
            "name": "release_capabilities",
            "description": (
                "Release active tool capabilities for a specific domain to save token space. "
                f"Currently active domains: {', '.join(self.active_domains) or 'none'}."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "The domain to release (e.g. 'filesystem', 'database')",
                    }
                },
                "required": ["domain"],
            },
        }

    def get_search_tool_schema(self) -> dict[str, Any]:
        """Return the schema for the `search_tools` meta-tool."""
        return {
            "name": "search_tools",
            "description": (
                "Search available tools semantically based on a natural language query. "
                "Dynamically activates and returns matching tool schemas."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query describing what you want to do (e.g. 'run terminal commands', 'edit python code')",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of tools to return (default: 3)",
                        "default": 3,
                    }
                },
                "required": ["query"],
            },
        }

    def search_tools(self, query: str, embedder: Any, top_k: int = 3) -> list[dict[str, Any]]:
        """
        Search for tool schemas semantically.
        Dynamically activates matching tools and returns their schemas.
        """
        all_tools = []
        for group in self._domains.values():
            all_tools.extend(group.tools)

        if not all_tools:
            return []

        # Build documents
        tool_texts = [f"name: {t.name}\ndescription: {t.description}" for t in all_tools]

        # Embed all tools and query
        tool_embeddings = embedder.embed(tool_texts)
        query_embedding = embedder.embed_single(query)

        # Query vector store
        from models.vector_store import VectorStore
        store = VectorStore()
        store.add(tool_embeddings, [t.name for t in all_tools])
        results = store.query(query_embedding, top_k=top_k)

        # Activate the matched tools and collect schemas
        matched_tools = []
        for res in results:
            tool_name = res.document
            schema = next((t for t in all_tools if t.name == tool_name), None)
            if schema:
                self._active_schemas[schema.name] = schema
                matched_tools.append({
                    "name": schema.name,
                    "description": schema.description,
                    "input_schema": schema.input_schema,
                })

        _log.info(
            f"Semantic tool search for '{query}' activated {len(matched_tools)} tools"
        )
        return matched_tools
