"""Factory para crear orquestadores DeepAgents configurados dinámicamente.

Permite crear orquestadores con diferentes combinaciones de sub-agentes
y tools según el contexto (usuario, knowledge base, etc.).

DeepAgents best practices applied:
- Explicit task() delegation in system prompt
- Checkpointer & store with graceful fallback
- Subagent descriptions explain WHEN to delegate
- Tools registered via StructuredTool.from_function(coroutine=...)
"""

from deepagents import create_deep_agent

from src.ia.langchain_models import get_chat_model
from src.ia.subagents.registry import get_available_subagents, get_subagent_descriptions
from src.ia.tools import create_rag_tool, mcp_execute, browser_navigate
from src.ia.memory import get_checkpointer, get_store
from src.ia.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from src.core.logging import logging

logger = logging.getLogger(__name__)


def create_orchestrator(
    subagent_names: list[str] | None = None,
    knowledge_base_id: str | None = None,
    system_prompt_override: str | None = None,
):
    """Create a DeepAgents orchestrator with registered sub-agents.

    Args:
        subagent_names: Which sub-agents to include. None = all.
        knowledge_base_id: Optional KB ID to inject into RAG tool context.
        system_prompt_override: Optional custom system prompt.

    Returns:
        Compiled DeepAgent (LangGraph StateGraph) ready for streaming.
    """
    subagents = get_available_subagents(subagent_names)

    # Build tools list (orchestrator has direct access + sub-agents have their own)
    tools = [mcp_execute, browser_navigate]
    
    if knowledge_base_id:
        tools.append(create_rag_tool(knowledge_base_id))

    # Default system prompt with sub-agent descriptions injected
    if system_prompt_override:
        prompt = system_prompt_override
    else:
        prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(
            subagent_descriptions=get_subagent_descriptions()
        )

    logger.info(
        "Creating DeepAgents orchestrator with %d sub-agents and %d tools",
        len(subagents),
        len(tools),
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
