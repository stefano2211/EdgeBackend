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
from src.ia.tools import rag_retrieve, mcp_execute, browser_navigate, browser_click, browser_screenshot, browser_extract_text


def _build_industrial_subagent() -> dict:
    """Sub-agente Industrial: recuperación de datos con RAG + MCP."""
    return {
        "name": "industrial-agent",
        "description": INDUSTRIAL_AGENT_DESCRIPTION,
        "system_prompt": INDUSTRIAL_AGENT_SYSTEM_PROMPT,
        "tools": [rag_retrieve, mcp_execute],
        "model": get_chat_model(),  # Base model
    }


def _build_historical_subagent() -> dict:
    """Sub-agente Histórico: análisis de tendencias, sin tools, con LoRA."""
    return {
        "name": "historical-agent",
        "description": HISTORICAL_AGENT_DESCRIPTION,
        "system_prompt": HISTORICAL_AGENT_SYSTEM_PROMPT,
        "tools": [],  # No tools — pure reasoning
        "model": get_chat_model(adapter="historical"),  # LoRA adapter
    }


def _build_vl_subagent() -> dict:
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
SUBAGENT_BUILDERS: dict[str, Callable[[], dict]] = {
    "industrial": _build_industrial_subagent,
    "historical": _build_historical_subagent,
    "vl": _build_vl_subagent,
}


def get_available_subagents(names: list[str] | None = None) -> list[dict]:
    """Build subagent configs from registry.

    Args:
        names: Specific subagent names to include. If None, includes all.
    """
    names = names or list(SUBAGENT_BUILDERS.keys())
    return [SUBAGENT_BUILDERS[name]() for name in names if name in SUBAGENT_BUILDERS]


def get_subagent_descriptions() -> str:
    """Generate descriptions string for orchestrator system prompt."""
    lines = []
    for name, builder in SUBAGENT_BUILDERS.items():
        cfg = builder()
        lines.append(f"- {cfg['name']}: {cfg['description']}")
    return "\n".join(lines)
