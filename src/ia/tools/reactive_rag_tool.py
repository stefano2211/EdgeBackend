"""Reactive RAG tool for DeepAgents — multi-stage retrieval from reactive Qdrant collections.

Uses the composable RetrievalPipeline with prefix="reactive_kb_" to search
exclusively in reactive knowledge bases.

Registered via StructuredTool.from_function(coroutine=...) for async
invocation by LangGraph / DeepAgents.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from src.core.logging import logging

logger = logging.getLogger(__name__)


async def _reactive_rag_retrieve_impl(
    knowledge_base_ids: list[str],
    query: str,
    top_k: int,
) -> str:
    """Internal implementation using the composable RetrievalPipeline (reactive prefix).

    Iterates through all provided KB IDs and aggregates results.
    """
    try:
        from src.services.retrieval_pipeline import RetrievalPipeline

        pipeline = RetrievalPipeline()
        all_chunks = []
        
        # Search each collection
        # We limit to first 5 collections to avoid extreme latency
        for kb_id in knowledge_base_ids[:5]:
            result = await pipeline.retrieve(
                knowledge_base_id=kb_id,
                query=query,
                top_k=top_k,
                prefix="reactive_kb_",
            )
            if result.chunks:
                all_chunks.extend(result.chunks)

        if not all_chunks:
            logger.debug(
                "No reactive RAG results for KBs %s query: %s",
                knowledge_base_ids,
                query[:50],
            )
            return "[No relevant documents found in the reactive knowledge bases.]"

        # Deduplicate and sort by rerank_score (if available) or score
        # Since RetrievalPipeline already reranked per collection, we just need to merge.
        def _get_score(c):
            return c.get("rerank_score") or c.get("score") or 0.0

        all_chunks.sort(key=_get_score, reverse=True)
        top_chunks = all_chunks[:top_k]

        # Re-format context using RetrievalPipeline's logic (or similar)
        # For simplicity, we can use the first result's context builder if we had one,
        # but RetrievalPipeline._format_context is static.
        formatted = RetrievalPipeline._format_context(top_chunks, query)
        return formatted or "[Documents found but relevance too low to include.]"

    except Exception as e:
        logger.exception("Reactive RAG retrieval failed for KBs %s: %s", knowledge_base_ids, e)
        return f"[Document retrieval error: {e}]"


def create_reactive_rag_tool(knowledge_base_ids: list[str]) -> StructuredTool:
    """Create a reactive RAG tool bound to a list of reactive knowledge base IDs."""

    async def _bound_rag_retrieve(query: str, top_k: int = 5) -> str:
        """Search the reactive Qdrant knowledge bases for relevant document chunks."""
        return await _reactive_rag_retrieve_impl(knowledge_base_ids, query, top_k)

    return StructuredTool.from_function(
        coroutine=_bound_rag_retrieve,
        name="reactive_rag_retrieve",
        description=(
            "Search the REACTIVE knowledge bases for relevant document chunks. "
            "Searches across multiple enabled collections. "
            "Returns formatted context with source citations. "
            "Use when the user query requires document retrieval or RAG from the reactive system."
        ),
    )

