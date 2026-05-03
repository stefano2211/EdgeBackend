"""RAG tool for DeepAgents — wraps our existing async Qdrant retrieval.

Uses StructuredTool.from_function with coroutine= to register the async
function directly with LangGraph / DeepAgents.
"""

from langchain_core.tools import StructuredTool

from src.core.logging import logging
from src.ia.rag_tool import rag_retrieve as _async_rag_retrieve

logger = logging.getLogger(__name__)


async def _rag_retrieve(
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
) -> str:
    """Search the Qdrant vector store for relevant documents.

    Args:
        knowledge_base_id: The knowledge base collection to search (e.g. "kb_42").
        query: The search query in natural language.
        top_k: Number of top results to return (default 5, max 20).

    Returns:
        Formatted context string with source documents, chunk text,
        and metadata (filename, page number, chunk index).
        Returns a note if no results are found.
    """
    result = await _async_rag_retrieve(knowledge_base_id, query, top_k)
    if result is None:
        return "[No relevant documents found in the knowledge base.]"
    return result


# Register as a LangChain tool usable by DeepAgents
rag_retrieve = StructuredTool.from_function(
    coroutine=_rag_retrieve,
    name="rag_retrieve",
    description=(
        "Search the Qdrant knowledge base for relevant document chunks. "
        "Returns formatted context with source citations. "
        "Use when the user query requires document retrieval or RAG."
    ),
)
