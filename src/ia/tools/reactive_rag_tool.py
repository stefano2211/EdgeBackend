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
    knowledge_base_id: str,
    query: str,
    top_k: int,
) -> str:
    """Internal implementation using the composable RetrievalPipeline (reactive prefix).

    Pipeline stages:
    1. Query Enhancement (multi-query + HyDE)
    2. Dense + Sparse embedding
    3. Hybrid search with RRF fusion in Qdrant (collection: reactive_kb_{id})
    4. Cross-Encoder reranking for precision
    5. Context formatting with source citations
    """
    try:
        from src.services.retrieval_pipeline import RetrievalPipeline

        pipeline = RetrievalPipeline()
        result = await pipeline.retrieve(
            knowledge_base_id=knowledge_base_id,
            query=query,
            top_k=top_k,
            prefix="reactive_kb_",
        )

        if not result.chunks:
            logger.debug(
                "No reactive RAG results for KB %s query: %s",
                knowledge_base_id,
                query[:50],
            )
            return "[No relevant documents found in the reactive knowledge base.]"

        if result.context is None:
            return "[Documents found but relevance too low to include.]"

        return result.context

    except Exception as e:
        logger.exception("Reactive RAG retrieval failed for KB %s: %s", knowledge_base_id, e)
        return f"[Document retrieval error: {e}]"


def create_reactive_rag_tool(knowledge_base_id: str) -> StructuredTool:
    """Create a reactive RAG tool bound to a specific reactive knowledge base ID."""

    async def _bound_rag_retrieve(query: str, top_k: int = 5) -> str:
        """Search the reactive Qdrant knowledge base for relevant document chunks."""
        return await _reactive_rag_retrieve_impl(knowledge_base_id, query, top_k)

    return StructuredTool.from_function(
        coroutine=_bound_rag_retrieve,
        name="reactive_rag_retrieve",
        description=(
            "Search the REACTIVE knowledge base for relevant document chunks. "
            "Uses hybrid search (dense + BM25 sparse) with cross-encoder reranking "
            "for high-precision retrieval. Returns formatted context with source "
            "citations including rank, score, rerank_score, filename, and page number. "
            "Use when the user query requires document retrieval or RAG from the reactive system."
        ),
    )
