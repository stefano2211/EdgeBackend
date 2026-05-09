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
from src.ia.tools import create_rag_tool, mcp_execute
from src.ia.memory import get_checkpointer, get_store
from src.ia.prompts.orchestrator import build_orchestrator_prompt
from src.ia.prompts.reactive import build_reactive_synthesis_prompt
from src.core.logging import logging

logger = logging.getLogger(__name__)


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
    subagents = get_available_subagents(
        subagent_names,
        knowledge_base_id=knowledge_base_id if enable_knowledge else None,
        enable_mcp=enable_mcp,
    )

    # Build tools list — only register tools that the user has enabled.
    # The orchestrator has direct access to these; sub-agents have their own.
    tools = []  # browser tools delegated to vl-agent

    if enable_mcp:
        tools.append(mcp_execute)

    if enable_knowledge and knowledge_base_id:
        tools.append(create_rag_tool(knowledge_base_id))

    # Build active tool names for dynamic prompt generation
    active_tool_names = [t.name for t in tools]

    # Default system prompt — built dynamically to only mention available tools
    if system_prompt_override:
        prompt = system_prompt_override
    else:
        prompt = build_orchestrator_prompt(
            subagent_descriptions=get_subagent_descriptions(),
            active_tool_names=active_tool_names,
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

    # Resolve checkpointer & store with graceful fallback
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
    knowledge_base_ids: list[int] | None = None,
    enable_knowledge: bool = True,
    enable_mcp: bool = True,
    enabled_tool_names: list[int] | None = None,
    system_prompt_override: str | None = None,
):
    """Create a DeepAgents orchestrator for the reactive event pipeline.

    DIFFERENT from chat orchestrator:
    - System-2 (this orchestrator) does triage + synthesis.
    - Sub-agent: s1-coordinator (fast intuition via historical + vl).
    - Direct tools: mcp_execute + rag_retrieve (industrial data for S2).

    Args:
        knowledge_base_ids: Optional list of KB IDs for RAG.
        enable_knowledge: Whether to enable RAG tool.
        enable_mcp: Whether to enable MCP tools.
        enabled_tool_names: Optional list of tool IDs to limit MCP tools.
        system_prompt_override: Optional custom system prompt for synthesis.

    Returns:
        Compiled DeepAgent ready for streaming.
    """
    # Pick the first KB ID for subagent compatibility (DeepAgents expects single str)
    kb_id_for_subagent = None
    if enable_knowledge and knowledge_base_ids:
        kb_id_for_subagent = str(knowledge_base_ids[0])

    subagents = get_available_subagents(
        names=["s1-coordinator"],
        knowledge_base_id=kb_id_for_subagent,
        enable_mcp=enable_mcp,
    )

    tools = []
    if enable_mcp:
        tools.append(mcp_execute)
    # NOTE: only bind the first KB for now to avoid duplicate tool names
    if enable_knowledge and knowledge_base_ids:
        tools.append(create_rag_tool(str(knowledge_base_ids[0])))

    active_tool_names = [t.name for t in tools]

    if system_prompt_override:
        prompt = system_prompt_override
    else:
        prompt = build_reactive_synthesis_prompt(
            active_tool_names=active_tool_names,
        )

    logger.info(
        "Creating Reactive DeepAgents orchestrator | sub-agents=%d tools=%d "
        "enable_knowledge=%s enable_mcp=%s active_tools=%s",
        len(subagents),
        len(tools),
        enable_knowledge,
        enable_mcp,
        active_tool_names,
    )

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
