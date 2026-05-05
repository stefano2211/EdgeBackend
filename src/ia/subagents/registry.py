"""Registry de sub-agentes configurables para DeepAgents.

Cada equipo puede agregar un sub-agente nuevo aquí sin modificar
el código del orquestador. El orquestador los descubre automáticamente
via el built-in `task` tool de DeepAgents.
"""

from collections.abc import Callable

from src.ia.langchain_models import get_chat_model
from src.ia.prompts.subagents import (
    INDUSTRIAL_AGENT_DESCRIPTION,
    INDUSTRIAL_AGENT_SYSTEM_PROMPT,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    VL_AGENT_DESCRIPTION,
    VL_AGENT_SYSTEM_PROMPT,
)
from src.ia.tools import create_rag_tool, mcp_execute, browser_navigate, browser_click, browser_type, browser_screenshot, browser_extract_text


def _build_industrial_subagent(
    knowledge_base_id: str | None = None,
    enable_mcp: bool = True,
) -> dict:
    """Sub-agente Industrial: recuperación de datos con RAG + MCP.

    Tools are conditionally registered based on user toggles:
    - mcp_execute: only if enable_mcp=True
    - rag_retrieve: only if knowledge_base_id is provided
    """
    tools = []
    if enable_mcp:
        tools.append(mcp_execute)
    if knowledge_base_id:
        tools.append(create_rag_tool(knowledge_base_id))

    return {
        "name": "industrial-agent",
        "description": INDUSTRIAL_AGENT_DESCRIPTION,
        "system_prompt": INDUSTRIAL_AGENT_SYSTEM_PROMPT,
        "tools": tools,
        "model": get_chat_model(),  # Base model
    }


def _build_historical_subagent(knowledge_base_id: str | None = None) -> dict:
    """Sub-agente Histórico: análisis de tendencias, sin tools, con LoRA."""
    return {
        "name": "historical-agent",
        "description": HISTORICAL_AGENT_DESCRIPTION,
        "system_prompt": HISTORICAL_AGENT_SYSTEM_PROMPT,
        "tools": [],  # No tools — pure reasoning
        "model": get_chat_model(adapter="historical"),  # LoRA adapter
    }


def _build_vl_subagent(knowledge_base_id: str | None = None) -> dict:
    """Sub-agente VL: navegación web, screenshots, visión."""
    return {
        "name": "vl-agent",
        "description": VL_AGENT_DESCRIPTION,
        "system_prompt": VL_AGENT_SYSTEM_PROMPT,
        "tools": [
            browser_navigate,
            browser_click,
            browser_type,
            browser_screenshot,
            browser_extract_text,
        ],
        "model": get_chat_model(adapter="vl"),  # Vision LoRA adapter
    }


# ── Registry público ──
# Agregar nuevos sub-agentes aquí — el orquestador los descubre automáticamente
SUBAGENT_BUILDERS: dict[str, Callable[[str | None], dict]] = {
    "industrial": _build_industrial_subagent,
    "historical": _build_historical_subagent,
    "vl": _build_vl_subagent,
}


def get_available_subagents(
    names: list[str] | None = None,
    knowledge_base_id: str | None = None,
    enable_mcp: bool = True,
) -> list[dict]:
    """Build subagent configs from registry.

    Args:
        names: Specific subagent names to include. If None, includes all.
        knowledge_base_id: Optional ID to bind to sub-agent tools.
        enable_mcp: Whether to enable MCP tools on the industrial sub-agent.
    """
    names = names or list(SUBAGENT_BUILDERS.keys())
    result = []
    for name in names:
        if name not in SUBAGENT_BUILDERS:
            continue
        if name == "industrial":
            result.append(SUBAGENT_BUILDERS[name](knowledge_base_id, enable_mcp=enable_mcp))
        else:
            result.append(SUBAGENT_BUILDERS[name](knowledge_base_id))
    return result


def get_subagent_descriptions(knowledge_base_id: str | None = None) -> str:
    """Generate descriptions string for orchestrator system prompt."""
    lines = []
    for name, builder in SUBAGENT_BUILDERS.items():
        cfg = builder(knowledge_base_id)
        lines.append(f"- {cfg['name']}: {cfg['description']}")
    return "\n".join(lines)
