"""Unified RAG tool factory.

Replaces: rag_tool.py + reactive_rag_tool.py
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from backend.core.logging import logging

logger = logging.getLogger(__name__)


async def _rag_retrieve_impl(
    knowledge_base_ids: list[str],
    query: str,
    top_k: int,
    prefix: str,
    context: str | None,
) -> str:
    """Internal implementation using RetrievalPipeline."""
    try:
        from backend.services.retrieval_pipeline import RetrievalPipeline

        pipeline = RetrievalPipeline()
        all_chunks = []

        for kb_id in knowledge_base_ids[:5]:
            result = await pipeline.retrieve(
                knowledge_base_id=kb_id,
                query=query,
                top_k=top_k,
                prefix=prefix,
                context=context,
            )
            if result.chunks:
                all_chunks.extend(result.chunks)

        if not all_chunks:
            logger.debug(
                "No RAG results for KBs %s (prefix=%s, context=%s) query: %s",
                knowledge_base_ids,
                prefix,
                context,
                query[:50],
            )
            return "[No relevant documents found.]"

        def _get_score(c):
            return c.get("rerank_score") or c.get("score") or 0.0

        all_chunks.sort(key=_get_score, reverse=True)
        top_chunks = all_chunks[:top_k]

        formatted = RetrievalPipeline._format_context(top_chunks, query)
        return formatted or "[Documents found but relevance too low.]"

    except Exception as e:
        logger.exception("RAG retrieval failed: %s", e)
        return f"[Document retrieval error: {e}]"


def create_rag_tool(
    knowledge_base_ids: list[str],
    prefix: str = "kb_",
    context: str | None = None,
) -> StructuredTool:
    """Create a RAG tool bound to knowledge base IDs and collection prefix.

    Args:
        knowledge_base_ids: List of KB IDs to search across.
        prefix: Qdrant collection prefix. "kb_" for chat, "reactive_kb_" for events.
        context: Optional context tag to filter chunks ("chat" or "reactive").

    Returns:
        StructuredTool ready for DeepAgents registration.
    """

    async def _bound_rag_retrieve(query: str, top_k: int = 5) -> str:
        """Search knowledge bases for relevant document chunks."""
        return await _rag_retrieve_impl(knowledge_base_ids, query, top_k, prefix, context)

    return StructuredTool.from_function(
        coroutine=_bound_rag_retrieve,
        name="rag_retrieve",
        description=(
            "Search the knowledge base for relevant document chunks. "
            "Uses hybrid search (dense + BM25 sparse) with cross-encoder reranking. "
            "Returns formatted context with source citations."
        ),
    )
