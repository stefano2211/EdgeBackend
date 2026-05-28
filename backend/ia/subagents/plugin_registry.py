"""Subagent plugin registry — auto-discoverable, context-aware.

Replaces registry.py + reactive_registry.py duplication.

To add a new subagent:
  1. Define a builder in builders.py.
  2. Call register() with a SubagentPlugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from backend.core.logging import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubagentPlugin:
    name: str
    description: str
    builder: Callable[..., dict]
    applies_to: set[str] = field(default_factory=lambda: {"proactive", "reactive"})
    requires_rag: bool = True
    requires_mcp: bool = True


class SubagentRegistry:
    _plugins: dict[str, SubagentPlugin] = {}

    @classmethod
    def register(cls, plugin: SubagentPlugin) -> None:
        cls._plugins[plugin.name] = plugin
        logger.info("[SubagentRegistry] Registered: %s", plugin.name)

    @classmethod
    def get_plugin(cls, name: str) -> SubagentPlugin | None:
        return cls._plugins.get(name)

    @classmethod
    def build_all(
        cls,
        context: Literal["proactive", "reactive"],
        *,
        kb_ids: list[str] | None = None,
        kb_names: list[str] | None = None,
        tool_names: list[str] | None = None,
        tool_schemas: list[dict] | None = None,
        enable_mcp: bool = True,
        enable_knowledge: bool = True,
    ) -> list[dict]:
        """Build subagent configs for the given context.

        Args:
            context: 'proactive' or 'reactive'.
            kb_ids: Knowledge base IDs for RAG tool binding.
            kb_names: Knowledge base names for prompt injection.
            tool_names: Optional filter for MCP tool names.
            tool_schemas: List of {name, description, parameter_schema} dicts
                          for dynamic MCP prompt injection.
            enable_mcp: Whether MCP tools are enabled.
            enable_knowledge: Whether RAG tools are enabled.
        """
        result = []
        for plugin in cls._plugins.values():
            if context not in plugin.applies_to:
                continue

            # Build tools list based on plugin requirements + caller toggles
            tools = []
            if plugin.requires_mcp and enable_mcp:
                from backend.ia.tools.unified.mcp import create_mcp_tool
                mcp_source = "chat" if context == "proactive" else context
                tools.append(create_mcp_tool(source=mcp_source))
            if plugin.requires_rag and enable_knowledge and kb_ids:
                from backend.ia.tools.unified.rag import create_rag_tool
                rag_context = "reactive" if context == "reactive" else "chat"
                tools.append(create_rag_tool(kb_ids, prefix="kb_", context=rag_context))

            cfg = plugin.builder(
                context=context,
                tools=tools,
                kb_ids=kb_ids,
                kb_names=kb_names,
                tool_schemas=tool_schemas,
            )
            result.append(cfg)
        return result

    @classmethod
    def get_descriptions(cls, names: list[str] | None = None) -> str:
        """Generate description string for orchestrator prompts."""
        lines = []
        for name, plugin in cls._plugins.items():
            if names and name not in names:
                continue
            lines.append(f"- {plugin.name}: {plugin.description}")
        return "\n".join(lines)

    @classmethod
    def list_registered(cls) -> list[str]:
        return list(cls._plugins.keys())
