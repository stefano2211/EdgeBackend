"""RAG tool for DeepAgents — real document retrieval from Qdrant.

Orchestrates: embed query → search vectors → format context for LLM.
Registered via StructuredTool.from_function(coroutine=...) for async
invocation by LangGraph / DeepAgents.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from src.core.logging import logging
from src.services.embedding_service import embed_query
from src.persistencia.vector import VectorRepository

logger = logging.getLogger(__name__)

# Confidence threshold: chunks below this score are dropped
_MIN_RELEVANCE_SCORE = 0.35


def _format_context(results: list[dict], query: str, *, min_score: float = _MIN_RELEVANCE_SCORE) -> str | None:
    """Format retrieved chunks into a context string for the LLM.

    Drops low-relevance chunks and orders by score (descending).
    Includes page numbers and source filenames for traceability.
    """
    filtered = [r for r in results if r.get("score", 0.0) >= min_score]
    if not filtered:
        logger.debug("All RAG chunks scored below %.2f; dropping context", min_score)
        return None

    filtered.sort(key=lambda r: r.get("score", 0.0), reverse=True)

    sources: list[str] = []
    for i, r in enumerate(filtered, start=1):
        filename = r.get("filename") or "unknown"
        page = r.get("page_number")
        score = r.get("score", 0.0)

        attrs = f'rank="{i}" doc="{filename}" score="{score:.3f}"'
        if page is not None:
            attrs += f' page="{page}"'

        sources.append(
            f"<source {attrs}>\n"
            f"[Chunk {r.get('chunk_index', '?')}]: {r['text']}\n"
            f"</source>"
        )

    context = "\n\n".join(sources)

    return (
        "You are a helpful assistant. Answer the question using ONLY the "
        "retrieved sources below. If the answer is not found in the sources, "
        "say you do not know. Do not make up facts.\n\n"
        f"Sources:\n{context}\n\n"
        f"Question: {query}"
    )


async def _rag_retrieve_impl(
    knowledge_base_id: str,
    query: str,
    top_k: int,
    vector_repo: Any | None,
) -> str:
    """Internal implementation with DI support."""
    repo = vector_repo if vector_repo is not None else VectorRepository()
    try:
        query_embedding = await embed_query(query)

        results = await repo.search_chunks(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not results:
            logger.debug("No RAG results for KB %s query: %s", knowledge_base_id, query[:50])
            return "[No relevant documents found in the knowledge base.]"

        context = _format_context(results, query)
        if context is None:
            return "[Documents found but relevance too low to include.]"
        return context

    except Exception as e:
        logger.exception("RAG retrieval failed for KB %s: %s", knowledge_base_id, e)
        return f"[Document retrieval error: {e}]"


async def _rag_retrieve(
    knowledge_base_id: str,
    query: str,
    top_k: int = 5,
) -> str:
    """Search Qdrant for relevant document chunks and return formatted context.

    Args:
        knowledge_base_id: Target knowledge base / Qdrant collection.
        query: User query string.
        top_k: Number of chunks to retrieve.

    Returns:
        Formatted context string, or a note if no relevant chunks found.
        Never raises — returns a fallback message on any error.
    """
    return await _rag_retrieve_impl(knowledge_base_id, query, top_k, vector_repo=None)


# Register as a LangChain tool usable by DeepAgents
rag_retrieve = StructuredTool.from_function(
    coroutine=_rag_retrieve,
    name="rag_retrieve",
    description=(
        "Search the Qdrant knowledge base for relevant document chunks. "
        "Returns formatted context with source citations including rank, score, "
        "filename, and page number. Use when the user query requires document retrieval or RAG."
    ),
)
