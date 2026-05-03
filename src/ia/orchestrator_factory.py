"""Factory para crear orquestadores DeepAgents configurados dinámicamente.

Permite crear orquestadores con diferentes combinaciones de sub-agentes
y tools según el contexto (usuario, knowledge base, etc.).
"""

from deepagents import create_deep_agent

from src.ia.langchain_models import get_chat_model
from src.ia.subagents.registry import get_available_subagents, get_subagent_descriptions
from src.ia.tools import rag_retrieve, mcp_execute, browser_navigate
from src.ia.memory import get_checkpointer, get_store
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
    tools = [rag_retrieve, mcp_execute, browser_navigate]

    # Default system prompt with sub-agent descriptions injected
    if system_prompt_override:
        prompt = system_prompt_override
    else:
        prompt = (
            "You are an intelligent task orchestrator. "
            "Your job is to analyze user requests and delegate to the most "
            "appropriate specialized sub-agent or tool.\n\n"
            "Available sub-agents (invoke via the built-in task tool):\n"
            f"{get_subagent_descriptions()}\n\n"
            "Available direct tools:\n"
            "- rag_retrieve: Search documents in the knowledge base\n"
            "- mcp_execute: Execute registered MCP/API tools\n"
            "- browser_navigate: Navigate to a web URL\n\n"
            "Guidelines:\n"
            "1. For document search + API queries, use the industrial-agent\n"
            "2. For historical analysis and trends, use the historical-agent\n"
            "3. For web navigation and visual tasks, use the vl-agent\n"
            "4. For simple tasks, use direct tools instead of sub-agents\n"
            "5. Always be concise and accurate. Cite sources when possible."
        )

    logger.info(
        "Creating DeepAgents orchestrator with %d sub-agents and %d tools",
        len(subagents),
        len(tools),
    )

    return create_deep_agent(
        model=get_chat_model(),
        system_prompt=prompt,
        subagents=subagents,
        tools=tools,
        checkpointer=get_checkpointer(),
        store=get_store(),
    )
