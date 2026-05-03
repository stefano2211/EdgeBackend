"""Registry de sub-agentes configurables para DeepAgents.

Cada equipo puede agregar un sub-agente nuevo aquí sin modificar
el código del orquestador. El orquestador los descubre automáticamente
via el built-in `task` tool de DeepAgents.
"""

from collections.abc import Callable

from src.ia.langchain_models import get_chat_model
from src.ia.tools import rag_retrieve, mcp_execute, browser_navigate, browser_click, browser_screenshot, browser_extract_text


def _build_industrial_subagent() -> dict:
    """Sub-agente Industrial: recuperación de datos con RAG + MCP."""
    return {
        "name": "industrial-agent",
        "description": (
            "Industrial data retrieval expert. Use for: "
            "searching documents in knowledge bases (RAG), "
            "querying external APIs and databases via MCP tools, "
            "and combining document search with API data. "
            "Has access to rag_retrieve and mcp_execute tools."
        ),
        "system_prompt": (
            "You are an industrial data retrieval specialist. "
            "Your job is to find relevant information from documents and external systems. "
            "You can search knowledge bases using RAG and query APIs using MCP tools. "
            "Always cite your sources and be precise with technical data. "
            "When you find the answer, return a concise summary with references."
        ),
        "tools": [rag_retrieve, mcp_execute],
        "model": get_chat_model(),  # Base model
    }


def _build_historical_subagent() -> dict:
    """Sub-agente Histórico: análisis de tendencias, sin tools, con LoRA."""
    return {
        "name": "historical-agent",
        "description": (
            "Historical data analysis expert. Use for: "
            "analyzing trends, quarter-over-quarter comparisons, "
            "historical pattern detection, and domain-specific insights. "
            "Has NO external tools — reasons purely from fine-tuned knowledge. "
            "Load the historical LoRA adapter for best results."
        ),
        "system_prompt": (
            "You are a historical data analysis expert with deep domain knowledge. "
            "You analyze trends, patterns, and historical performance data. "
            "You do not have access to external tools or web browsing. "
            "Provide thorough, data-backed insights with clear reasoning."
        ),
        "tools": [],  # No tools — pure reasoning
        "model": get_chat_model(adapter="historical"),  # LoRA adapter
    }


def _build_vl_subagent() -> dict:
    """Sub-agente VL: navegación web, screenshots, visión."""
    return {
        "name": "vl-agent",
        "description": (
            "Vision-language web automation expert. Use for: "
            "navigating websites, interacting with web UIs, "
            "taking screenshots, filling forms, clicking buttons, "
            "and visual verification of web applications "
            "(Gmail, SAP, enterprise portals). "
            "Has access to browser navigation and interaction tools. "
            "Load the vision LoRA adapter for best results."
        ),
        "system_prompt": (
            "You are a web automation and vision-language expert. "
            "You can navigate websites, interact with UI elements, "
            "take screenshots, fill forms, and click buttons. "
            "Always describe what you see and what actions you take. "
            "Be careful with sensitive operations. "
            "When finished, summarize what you found or accomplished."
        ),
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
