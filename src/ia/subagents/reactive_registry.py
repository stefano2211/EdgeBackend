"""Reactive sub-agent registry — isolated from chat sub-agents.

Each builder creates sub-agents wired exclusively to reactive resources:
- Reactive RAG tool (reactive_kb_* Qdrant collections)
- Reactive MCP tool (reactive_tool_configs table)
- Reactive browser tools (BrowserManager "reactive" instance)

The orchestrator discovers them automatically via the built-in task() tool.
"""

from collections.abc import Callable

from src.core.logging import logging
from src.ia.langchain_models import get_chat_model, get_multimodal_chat_model
from src.ia.prompts.subagents import (
    INDUSTRIAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    VL_AGENT_DESCRIPTION,
    VL_AGENT_SYSTEM_PROMPT,
    build_industrial_agent_prompt,
)
from src.ia.prompts.reactive import (
    REACTIVE_S1_COORDINATOR_PROMPT,
    S1_COORDINATOR_DESCRIPTION,
)
from src.ia.tools.reactive_rag_tool import create_reactive_rag_tool
from src.ia.tools.reactive_mcp_tool import reactive_mcp_execute
from src.ia.tools.reactive_web_browser import (
    reactive_browser_navigate,
    reactive_browser_dom,
    reactive_computer,
)

logger = logging.getLogger(__name__)


# ── Reactive builders ──


def _build_reactive_industrial_subagent(
    knowledge_base_ids: list[str] | None = None,
    enable_mcp: bool = True,
    mcp_tool_names: list[str] | None = None,
) -> dict:
    """Reactive industrial-agent: RAG + MCP from reactive tables/collections."""
    tools = []
    has_mcp = enable_mcp and (mcp_tool_names is None or len(mcp_tool_names) > 0)
    has_rag = knowledge_base_ids is not None and len(knowledge_base_ids) > 0

    if has_mcp:
        tools.append(reactive_mcp_execute)
    if has_rag:
        tools.append(create_reactive_rag_tool(knowledge_base_ids))

    # Generate dynamic system prompt
    system_prompt = build_industrial_agent_prompt(
        has_rag=has_rag,
        has_mcp=has_mcp,
        rag_collections=knowledge_base_ids,  # Using IDs as names for now, or could fetch actual names
        mcp_tools=mcp_tool_names,
        is_reactive=True,
    )

    return {
        "name": "industrial-agent",
        "description": INDUSTRIAL_AGENT_DESCRIPTION,
        "system_prompt": system_prompt,
        "tools": tools,
        "model": get_chat_model(),
    }


def _build_reactive_historical_subagent(knowledge_base_ids: list[str] | None = None) -> dict:
    """Reactive historical-agent: trend analysis, no tools, with LoRA."""
    return {
        "name": "historical-agent",
        "description": HISTORICAL_AGENT_DESCRIPTION,
        "system_prompt": HISTORICAL_AGENT_SYSTEM_PROMPT,
        "tools": [],
        "model": get_chat_model(adapter="historical"),
    }


def _build_reactive_vl_subagent(knowledge_base_ids: list[str] | None = None) -> dict:
    """Reactive vl-agent: web navigation with isolated reactive browser."""
    logger.info("[Reactive VL-Subagent] Building with model=%s", get_multimodal_chat_model())
    return {
        "name": "vl-agent",
        "description": VL_AGENT_DESCRIPTION,
        "system_prompt": VL_AGENT_SYSTEM_PROMPT,
        "tools": [
            reactive_browser_navigate,
            reactive_browser_dom,
            reactive_computer,
        ],
        "model": get_multimodal_chat_model(),
    }


def _build_reactive_s1_coordinator(knowledge_base_ids: list[str] | None = None) -> dict:
    """Reactive S1 Coordinator: fast intuition via historical + vl (parallel).

    Uses the reactive vl-agent with the isolated browser instance.
    """
    return {
        "name": "s1-coordinator",
        "description": S1_COORDINATOR_DESCRIPTION,
        "system_prompt": REACTIVE_S1_COORDINATOR_PROMPT,
        "tools": [],
        "model": get_chat_model(),
        "subagents": [
            _build_reactive_historical_subagent(knowledge_base_ids),
            _build_reactive_vl_subagent(knowledge_base_ids),
        ],
    }


# ── Registry público ──

REACTIVE_SUBAGENT_BUILDERS: dict[str, Callable] = {
    "industrial": _build_reactive_industrial_subagent,
    "historical": _build_reactive_historical_subagent,
    "vl": _build_reactive_vl_subagent,
    "s1-coordinator": _build_reactive_s1_coordinator,
}


def get_reactive_subagents(
    names: list[str] | None = None,
    knowledge_base_ids: list[str] | None = None,
    enable_mcp: bool = True,
    mcp_tool_names: list[str] | None = None,
) -> list[dict]:
    """Build reactive subagent configs from registry.

    Args:
        names: Specific subagent names to include. If None, includes all.
        knowledge_base_ids: Optional IDs to bind to reactive sub-agent tools.
        enable_mcp: Whether to enable reactive MCP tools.
        mcp_tool_names: Optional list of specific MCP tool names.
    """
    names = names or list(REACTIVE_SUBAGENT_BUILDERS.keys())
    result = []
    for name in names:
        if name not in REACTIVE_SUBAGENT_BUILDERS:
            continue
        if name == "industrial":
            result.append(REACTIVE_SUBAGENT_BUILDERS[name](
                knowledge_base_ids=knowledge_base_ids, 
                enable_mcp=enable_mcp,
                mcp_tool_names=mcp_tool_names
            ))
        else:
            result.append(REACTIVE_SUBAGENT_BUILDERS[name](knowledge_base_ids=knowledge_base_ids))
    return result


def get_reactive_subagent_descriptions(
    names: list[str] | None = None,
    knowledge_base_ids: list[str] | None = None,
) -> str:
    """Generate descriptions string for reactive orchestrator system prompt.

    Args:
        names: Specific subagent names to describe. If None, describes all.
        knowledge_base_ids: Optional IDs passed to builders.
    """
    names = names or list(REACTIVE_SUBAGENT_BUILDERS.keys())
    lines = []
    for name in names:
        if name not in REACTIVE_SUBAGENT_BUILDERS:
            continue
        cfg = REACTIVE_SUBAGENT_BUILDERS[name](knowledge_base_ids=knowledge_base_ids)
        lines.append(f"- {cfg['name']}: {cfg['description']}")
    return "\n".join(lines)

