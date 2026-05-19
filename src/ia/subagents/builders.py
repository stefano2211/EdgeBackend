"""Subagent builders — parametrized by context.

Each builder receives (context, tools, kb_ids) and returns a DeepAgents subagent dict.
System prompts for MCP and RAG are built dynamically with tool/KB catalogs.
"""

from __future__ import annotations

from src.core.logging import logging
from src.ia.langchain_models import get_chat_model, get_multimodal_chat_model
from src.ia.prompts.subagents import (
    RAG_AGENT_DESCRIPTION,
    build_rag_system_prompt,
    MCP_AGENT_DESCRIPTION,
    build_mcp_system_prompt,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    VL_AGENT_DESCRIPTION,
    VL_AGENT_SYSTEM_PROMPT,
)
from src.ia.tools.credential_tool import get_secret_credential
from src.ia.tools.unified.computer import (
    create_computer_tool,
    create_browser_navigate_tool,
    create_browser_dom_tool,
)
from src.ia.subagents.plugin_registry import SubagentPlugin, SubagentRegistry

logger = logging.getLogger(__name__)


def _build_rag_subagent(
    context: str,
    tools: list,
    kb_ids: list[str] | None = None,
    kb_names: list[str] | None = None,
    **_,
) -> dict:
    # Build dynamic KB catalog for the prompt
    kb_catalog = ""
    if kb_names:
        lines = ["Active knowledge bases:\n"]
        for i, name in enumerate(kb_names, 1):
            lines.append(f"{i}. {name}")
        kb_catalog = "\n".join(lines)

    return {
        "name": "rag-agent",
        "description": RAG_AGENT_DESCRIPTION,
        "system_prompt": build_rag_system_prompt(kb_catalog=kb_catalog),
        "tools": tools,
        "model": get_chat_model(),
    }


def _build_mcp_subagent(
    context: str,
    tools: list,
    kb_ids: list[str] | None = None,
    tool_schemas: list[dict] | None = None,
    **_,
) -> dict:
    # Build dynamic tool catalog for the prompt
    tool_catalog = ""
    if tool_schemas:
        lines = ["Available tools (call via mcp_execute):\n"]
        for i, t in enumerate(tool_schemas, 1):
            name = t.get("name", "unknown")
            desc = t.get("description") or "No description provided."
            schema = t.get("parameter_schema") or {}

            line = f"{i}. {name} — {desc}"
            params = schema.get("parameters") or schema.get("properties")
            if params:
                param_parts = []
                for pname, pinfo in params.items():
                    ptype = pinfo.get("type", "any") if isinstance(pinfo, dict) else "any"
                    param_parts.append(f"{pname}: {ptype}")
                line += f"\n   Parameters: {{{', '.join(param_parts)}}}"

            lines.append(line)
        tool_catalog = "\n".join(lines)
    else:
        tool_catalog = (
            "No integration tools are currently registered.\n"
            "If a task requires external data or actions, report this limitation clearly."
        )

    return {
        "name": "mcp-agent",
        "description": MCP_AGENT_DESCRIPTION,
        "system_prompt": build_mcp_system_prompt(tool_catalog=tool_catalog),
        "tools": tools,
        "model": get_chat_model(),
    }


def _build_historical_subagent(
    context: str,
    tools: list,
    **_,
) -> dict:
    return {
        "name": "historical-agent",
        "description": HISTORICAL_AGENT_DESCRIPTION,
        "system_prompt": HISTORICAL_AGENT_SYSTEM_PROMPT,
        "tools": [],
        "model": get_chat_model(adapter="historical"),
    }


def _build_vl_subagent(
    context: str,
    tools: list,
    **_,
) -> dict:
    instance = "reactive" if context == "reactive" else "chat"
    logger.info("[VL-Subagent] Building for context=%s instance=%s", context, instance)
    return {
        "name": "vl-agent",
        "description": VL_AGENT_DESCRIPTION,
        "system_prompt": VL_AGENT_SYSTEM_PROMPT,
        "tools": [
            create_browser_navigate_tool(instance=instance),
            create_browser_dom_tool(instance=instance),
            create_computer_tool(instance=instance),
            get_secret_credential,
        ],
        "model": get_multimodal_chat_model(),
    }


# ── Auto-register on import ──
SubagentRegistry.register(SubagentPlugin(
    name="rag",
    description=RAG_AGENT_DESCRIPTION,
    builder=_build_rag_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=True,
    requires_mcp=False,
))

SubagentRegistry.register(SubagentPlugin(
    name="mcp",
    description=MCP_AGENT_DESCRIPTION,
    builder=_build_mcp_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=False,
    requires_mcp=True,
))

SubagentRegistry.register(SubagentPlugin(
    name="historical",
    description=HISTORICAL_AGENT_DESCRIPTION,
    builder=_build_historical_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=False,
    requires_mcp=False,
))

SubagentRegistry.register(SubagentPlugin(
    name="vl",
    description=VL_AGENT_DESCRIPTION,
    builder=_build_vl_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=False,
    requires_mcp=False,
))
