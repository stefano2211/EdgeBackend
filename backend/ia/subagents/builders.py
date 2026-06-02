"""Subagent builders — parametrized by context.

Each builder receives (context, tools, kb_ids) and returns a DeepAgents subagent dict.
System prompts for MCP and RAG are built dynamically with tool/KB catalogs.
"""

from __future__ import annotations

from backend.core.logging import logging
from backend.ia.langchain_models import get_chat_model
from backend.ia.prompts.subagents import (
    RAG_AGENT_DESCRIPTION,
    build_rag_system_prompt,
    MCP_AGENT_DESCRIPTION,
    build_mcp_system_prompt,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    DB_AGENT_DESCRIPTION,
    build_db_system_prompt,
    DATA_ANALYST_AGENT_DESCRIPTION,
    build_data_analyst_system_prompt,
)

from backend.ia.subagents.plugin_registry import SubagentPlugin, SubagentRegistry

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
    has_rest_tools = False
    if tool_schemas:
        lines = ["Available tools (call via mcp_execute):\n"]
        for i, t in enumerate(tool_schemas, 1):
            name = t.get("name", "unknown")
            desc = t.get("description") or "No description provided."
            schema = t.get("parameter_schema") or {}
            config = t.get("config") or {}
            transport = config.get("transport", "stdio")

            # Detect REST auto-discovered tools
            is_rest = transport == "rest" or bool(schema.get("filterable_schema"))
            if is_rest:
                has_rest_tools = True

            line = f"{i}. {name} — {desc}"
            line += f"\n   Transport: {transport.upper()}"

            # Input parameters
            params = schema.get("parameters") or schema.get("properties")
            if params:
                param_parts = []
                for pname, pinfo in params.items():
                    ptype = pinfo.get("type", "any") if isinstance(pinfo, dict) else "any"
                    param_parts.append(f"{pname}: {ptype}")
                line += f"\n   Input: {{{', '.join(param_parts)}}}"

            # REST-specific: response fields and filterable schema
            if is_rest:
                response_fields = schema.get("response") or {}
                if response_fields:
                    resp_parts = []
                    for fname, fdef in response_fields.items():
                        if isinstance(fdef, dict):
                            ftype = fdef.get("type", "any")
                            unit = fdef.get("unit", "")
                            fdesc = fdef.get("description", "")
                            unit_str = f", {unit}" if unit else ""
                            resp_parts.append(f"{fname} ({ftype}{unit_str}) — {fdesc}")
                        else:
                            resp_parts.append(f"{fname}: {fdef}")
                    if resp_parts:
                        line += "\n   Returns:\n      - " + "\n      - ".join(resp_parts)

                filterable = schema.get("filterable_schema") or {}
                if filterable:
                    kv = filterable.get("key_values") or {}
                    kf = filterable.get("key_figures") or []
                    filt_parts = []
                    if kv:
                        kv_str = ", ".join(f"{k}: {v}" for k, v in kv.items())
                        filt_parts.append(f"key_values: {{{kv_str}}}")
                    if kf:
                        filt_parts.append(f"key_figures: [{', '.join(str(x) for x in kf)}]")
                    if filt_parts:
                        line += "\n   Filterable:\n      - " + "\n      - ".join(filt_parts)

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
        "system_prompt": build_mcp_system_prompt(tool_catalog=tool_catalog, has_rest_tools=has_rest_tools),
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


def _build_db_subagent(
    context: str,
    tools: list,
    db_catalog: str = "",
    **_,
) -> dict:
    from backend.ia.tools.unified.db import create_db_query_tool, create_db_schema_tool

    # Get user_id from context or default to 1
    user_id = 1  # Will be resolved at runtime via the orchestrator

    db_tools = [
        create_db_query_tool(user_id=user_id, context=context),
        create_db_schema_tool(user_id=user_id, context=context),
    ]

    return {
        "name": "db-agent",
        "description": DB_AGENT_DESCRIPTION,
        "system_prompt": build_db_system_prompt(db_catalog=db_catalog),
        "tools": db_tools + tools,
        "model": get_chat_model(),
    }


def _build_data_analyst_subagent(
    context: str,
    tools: list,
    db_connection_ids: list[str] | None = None,
    **_,
) -> dict:
    from backend.ia.tools.unified.data_analyst import create_data_analyst_tools

    # user_id will be resolved at runtime via the orchestrator/config
    # For now we use 1 as placeholder (the tool factory accepts user_id)
    user_id = 1
    data_analyst_tools = create_data_analyst_tools(
        user_id=user_id, context=context, db_connection_ids=db_connection_ids
    )

    return {
        "name": "data-analyst-agent",
        "description": DATA_ANALYST_AGENT_DESCRIPTION,
        "system_prompt": build_data_analyst_system_prompt(),
        "tools": data_analyst_tools + tools,
        "model": get_chat_model(),
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
    name="db",
    description=DB_AGENT_DESCRIPTION,
    builder=_build_db_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=False,
    requires_mcp=False,
))

SubagentRegistry.register(SubagentPlugin(
    name="data_analyst",
    description=DATA_ANALYST_AGENT_DESCRIPTION,
    builder=_build_data_analyst_subagent,
    applies_to={"proactive", "reactive"},
    requires_rag=False,
    requires_mcp=False,
))


