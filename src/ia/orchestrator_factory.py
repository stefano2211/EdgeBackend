"""Factory para crear orquestadores DeepAgents configurados dinámicamente.

Permite crear orquestadores con diferentes combinaciones de sub-agentes
y tools según el contexto (usuario, knowledge base, etc.).

DeepAgents best practices applied:
- Explicit task() delegation in system prompt
- Checkpointer & store with graceful fallback
- Subagent descriptions explain WHEN to delegate
- Tools registered via StructuredTool.from_function(coroutine=...)
- Conditional tool registration based on user toggles (RAG/MCP)
"""

from deepagents import create_deep_agent

from src.ia.langchain_models import get_chat_model
from src.ia.subagents.registry import get_available_subagents, get_subagent_descriptions
from src.ia.subagents.reactive_registry import get_reactive_subagents, get_reactive_subagent_descriptions
from src.ia.tools import create_rag_tool, mcp_execute
from src.ia.memory import get_checkpointer, get_store
from src.ia.prompts.orchestrator import build_orchestrator_prompt
from src.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
from src.core.logging import logging

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
    subagent_names: list[str] | None = None,
    knowledge_base_id: str | None = None,
    system_prompt_override: str | None = None,
    enable_knowledge: bool = True,
    enable_mcp: bool = True,
):
    """Create a DeepAgents orchestrator with registered sub-agents.

    Args:
        subagent_names: Which sub-agents to include. None = all.
        knowledge_base_id: Optional KB ID to inject into RAG tool context.
        system_prompt_override: Optional custom system prompt.
        enable_knowledge: Whether to enable the RAG tool.
        enable_mcp: Whether to enable MCP tools.

    Returns:
        Compiled DeepAgent (LangGraph StateGraph) ready for streaming.
    """
    has_industrial = enable_mcp or enable_knowledge
    actual_subagent_names = subagent_names or ["industrial", "historical", "vl"]
    if not has_industrial and "industrial" in actual_subagent_names:
        actual_subagent_names.remove("industrial")

    subagents = get_available_subagents(
        names=actual_subagent_names,
        knowledge_base_id=knowledge_base_id if enable_knowledge else None,
        enable_mcp=enable_mcp,
    )

    # The main orchestrator has NO direct tools; it must delegate all work to sub-agents.
    tools = []
    active_tool_names = []

    # Default system prompt — built dynamically to only mention available tools
    if system_prompt_override:
        prompt = system_prompt_override
    else:
        prompt = build_orchestrator_prompt(
            subagent_descriptions=get_subagent_descriptions(actual_subagent_names),
            has_industrial=has_industrial,
        )

    logger.info(
        "Creating DeepAgents orchestrator | sub-agents=%d tools=%d "
        "enable_knowledge=%s enable_mcp=%s active_tools=%s",
        len(subagents),
        len(tools),
        enable_knowledge,
        enable_mcp,
        active_tool_names,
    )

    checkpointer, store = _resolve_memory()

    kwargs: dict = {
        "model": get_chat_model(),
        "system_prompt": prompt,
        "subagents": subagents,
        "tools": tools,
    }
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store

    return create_deep_agent(**kwargs)


def create_reactive_orchestrator(
    knowledge_base_ids: list[str] | None = None,
    enable_knowledge: bool = True,
    enable_mcp: bool = True,
    enabled_tool_names: list[str] | None = None,
    system_prompt_override: str | None = None,
):
    """Create a DeepAgents orchestrator for the reactive event pipeline.

    S2 is the SINGLE ENTRY POINT for reactive events. It autonomously decides
    which sub-agents to invoke via task() and synthesizes the results.

    Sub-agents registered (flat hierarchy, same as proactive):
    - industrial-agent: live sensor data (MCP) + SOPs/manuals (RAG)
    - historical-agent: LoRA pattern matching for past incidents
    - vl-agent: visual verification + web automation via isolated browser

    Args:
        knowledge_base_ids: Optional list of KB IDs for RAG.
        enable_knowledge: Whether to enable RAG tool.
        enable_mcp: Whether to enable MCP tools.
        enabled_tool_names: Optional list of tool names to limit MCP tools.
        system_prompt_override: Optional custom system prompt.

    Returns:
        Compiled DeepAgent ready for streaming.
    """
    # S2 has industrial-agent (data) only if tools are enabled + historical + vl directly
    has_industrial = enable_mcp or enable_knowledge
    subagent_names = ["historical", "vl"]
    if has_industrial:
        subagent_names.insert(0, "industrial")

    subagents = get_reactive_subagents(
        names=subagent_names,
        knowledge_base_ids=knowledge_base_ids if enable_knowledge else None,
        enable_mcp=enable_mcp,
        mcp_tool_names=enabled_tool_names,
    )


    # S2 has NO direct tools; it delegates to industrial-agent, historical-agent, and vl-agent.
    tools = []
    active_tool_names = []

    if system_prompt_override:
        prompt = system_prompt_override
    else:
        prompt = build_reactive_s2_orchestrator_prompt(
            has_industrial=has_industrial,
        )

    logger.info(
        "Creating Reactive S2 Orchestrator | sub-agents=%d tools=%d "
        "enable_knowledge=%s enable_mcp=%s active_tools=%s",
        len(subagents),
        len(tools),
        enable_knowledge,
        enable_mcp,
        active_tool_names,
    )

    checkpointer, store = _resolve_memory()

    kwargs: dict = {
        "model": get_chat_model(),
        "system_prompt": prompt,
        "subagents": subagents,
        "tools": tools,
    }
    if checkpointer is not None:
        kwargs["checkpointer"] = checkpointer
    if store is not None:
        kwargs["store"] = store

    return create_deep_agent(**kwargs)
