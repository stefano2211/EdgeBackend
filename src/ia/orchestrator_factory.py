"""Factory para crear orquestadores DeepAgents configurados dinámicamente.

Unified factory — eliminates duplication between proactive (chat) and reactive (event)
orchestrators via a single `create_orchestrator()` with a `context` parameter.

DeepAgents best practices applied:
- Explicit task() delegation in system prompt
- Checkpointer & store with graceful fallback
- Subagent descriptions explain WHEN to delegate
- Tools registered via StructuredTool.from_function(coroutine=...)
- Conditional tool registration based on user toggles (RAG/MCP)
"""

from __future__ import annotations

from typing import Literal

from deepagents import create_deep_agent

from src.core.logging import logging
from src.ia.langchain_models import get_chat_model
from src.ia.memory import get_checkpointer, get_store
from src.ia.prompts.orchestrator import build_orchestrator_prompt
from src.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
from src.ia.subagents.plugin_registry import SubagentRegistry
from src.ia.subagents.builders import *  # ensure plugins are registered

logger = logging.getLogger(__name__)


def _resolve_memory() -> tuple:
    """Resolve checkpointer & store with graceful fallback.

    Returns:
        (checkpointer, store) tuple where each may be None.
    """
    try:
        checkpointer = get_checkpointer()
    except RuntimeError:
        logger.warning("Checkpointer not initialized; DeepAgents will use default")
        checkpointer = None

    try:
        store = get_store()
    except RuntimeError:
        logger.warning("Store not initialized; DeepAgents will use default")
        store = None

    return checkpointer, store


def create_orchestrator(
    context: Literal["proactive", "reactive"] = "proactive",
    subagent_names: list[str] | None = None,
    knowledge_base_id: str | None = None,
    knowledge_base_ids: list[str] | None = None,
    system_prompt_override: str | None = None,
    enable_knowledge: bool = True,
    enable_mcp: bool = True,
    enabled_tool_names: list[str] | None = None,
):
    """Create a DeepAgents orchestrator with registered sub-agents.

    Args:
        context: 'proactive' for chat, 'reactive' for events.
        subagent_names: Which sub-agents to include. None = all applicable.
        knowledge_base_id: Single KB ID (proactive legacy).
        knowledge_base_ids: List of KB IDs (reactive).
        system_prompt_override: Optional custom system prompt.
        enable_knowledge: Whether to enable the RAG tool.
        enable_mcp: Whether to enable MCP tools.
        enabled_tool_names: Optional list of tool names to limit MCP tools.

    Returns:
        Compiled DeepAgent (LangGraph StateGraph) ready for streaming.
    """
    has_industrial = enable_mcp or enable_knowledge

    # Resolve KB IDs uniformly
    if context == "reactive":
        kb_ids = knowledge_base_ids if enable_knowledge else None
        default_names = ["historical", "vl"]
        if has_industrial:
            default_names.insert(0, "industrial")
    else:
        kb_ids = [knowledge_base_id] if (knowledge_base_id and enable_knowledge) else None
        default_names = ["industrial", "historical", "vl"]
        if not has_industrial and "industrial" in default_names:
            default_names.remove("industrial")

    actual_names = subagent_names or default_names

    subagents = SubagentRegistry.build_all(
        context=context,
        kb_ids=kb_ids,
        tool_names=enabled_tool_names,
        enable_mcp=enable_mcp,
        enable_knowledge=enable_knowledge,
    )
    # Filter to requested names
    subagents = [s for s in subagents if s.get("name", "").replace("-agent", "") in actual_names]

    # Build prompt
    if system_prompt_override:
        prompt = system_prompt_override
    elif context == "reactive":
        prompt = build_reactive_s2_orchestrator_prompt(has_industrial=has_industrial)
    else:
        prompt = build_orchestrator_prompt(
            subagent_descriptions=SubagentRegistry.get_descriptions(names=actual_names),
            has_industrial=has_industrial,
        )

    logger.info(
        "Creating DeepAgents orchestrator | context=%s sub-agents=%d "
        "enable_knowledge=%s enable_mcp=%s",
        context,
        len(subagents),
        enable_knowledge,
        enable_mcp,
    )

    checkpointer, store = _resolve_memory()

    kwargs: dict = {
        "model": get_chat_model(),
        "system_prompt": prompt,
        "subagents": subagents,
        "tools": [],  # orchestrator has no direct tools
    }
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store

    return create_deep_agent(**kwargs)


# ── Backwards-compatible aliases ──

def create_reactive_orchestrator(
    knowledge_base_ids: list[str] | None = None,
    enable_knowledge: bool = True,
    enable_mcp: bool = True,
    enabled_tool_names: list[str] | None = None,
    system_prompt_override: str | None = None,
):
    """Backward-compatible wrapper for reactive orchestrator creation."""
    return create_orchestrator(
        context="reactive",
        knowledge_base_ids=knowledge_base_ids,
        enable_knowledge=enable_knowledge,
        enable_mcp=enable_mcp,
        enabled_tool_names=enabled_tool_names,
        system_prompt_override=system_prompt_override,
    )
