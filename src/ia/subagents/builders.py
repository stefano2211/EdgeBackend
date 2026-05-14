"""Subagent builders — parametrized by context.

Each builder receives (context, tools, kb_ids) and returns a DeepAgents subagent dict.
"""

from __future__ import annotations

from src.core.logging import logging
from src.ia.langchain_models import get_chat_model, get_multimodal_chat_model
from src.ia.prompts.subagents import (
    INDUSTRIAL_AGENT_DESCRIPTION,
    INDUSTRIAL_AGENT_SYSTEM_PROMPT,
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


def _build_industrial_subagent(
    context: str,
    tools: list,
    kb_ids: list[str] | None = None,
    **_,
) -> dict:
    return {
        "name": "industrial-agent",
        "description": INDUSTRIAL_AGENT_DESCRIPTION,
        "system_prompt": INDUSTRIAL_AGENT_SYSTEM_PROMPT,
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
    name="industrial",
    description=INDUSTRIAL_AGENT_DESCRIPTION,
    builder=_build_industrial_subagent,
    applies_to={"proactive", "reactive"},
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
