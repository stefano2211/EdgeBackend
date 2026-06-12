"""Composable multi-stage retrieval pipeline (SOLID).

Orchestrates: enhance → embed → retrieve (hybrid) → rerank → format context.

Each stage is an injectable service following the Dependency Inversion Principle.
Stages can be toggled independently via settings. The pipeline follows the
Chain of Responsibility pattern where each stage processes the output of
the previous one.

Architecture:
    QueryEnhancer → EmbeddingService → VectorRepository (hybrid RRF) → Reranker → ContextBuilder
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from backend.core.config import settings
from backend.core.logging import logging
from backend.services.retrieval_metrics import RetrievalMetrics, StageTimer

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Structured output from the retrieval pipeline."""

    chunks: list[dict[str, Any]]
    context: str | None
    metrics: RetrievalMetrics


class RetrievalPipeline:
    """Composable multi-stage retrieval pipeline.

    Follows SOLID principles:
    - SRP: Each stage is a separate service.
    - OCP: New stages can be added without modifying existing ones.
    - LSP: All services implement their respective Protocols.
    - ISP: Ports expose only what each consumer needs.
    - DIP: Pipeline depends on abstractions (Protocols), not implementations.
    """

    def __init__(self) -> None:
        # Lazy imports to avoid circular dependencies and allow toggling
        from backend.persistencia.vector import VectorRepository
        from backend.services.embedding_service import embed_texts
        from backend.services.reranking_service import get_reranker
        from backend.services.query_enhancer import get_query_enhancer

        self._vector_repo = VectorRepository()
        self._embed_texts = embed_texts
        self._reranker = get_reranker()
        self._query_enhancer = get_query_enhancer()

        # Sparse embedder (conditional import)
        self._sparse_embed_texts = None
        if settings.HYBRID_SEARCH_ENABLED:
            try:
                from backend.services.sparse_embedding_service import embed_sparse_texts
                self._sparse_embed_texts = embed_sparse_texts
            except ImportError:
                logger.warning(
                    "fastembed not available; falling back to dense-only search"
                )

    async def retrieve(
        self,
        knowledge_base_id: str,
        query: str,
        top_k: int | None = None,
        filter_doc_ids: list[int | str] | None = None,
        prefix: str = "kb_",
        context_tag: str | None = None,
    ) -> RetrievalResult:
        """Execute the full retrieval pipeline.

        Stages:
        1. ENHANCE: Generate query variations (multi-query + HyDE)
        2. EMBED: Generate dense + sparse embeddings for all queries
        3. RETRIEVE: Hybrid search with RRF fusion in Qdrant
        4. RERANK: Cross-encoder precision filtering
        5. FORMAT: Build context string for the LLM

        Args:
            knowledge_base_id: Target knowledge base collection.
            query: The user's search query.
            top_k: Final number of chunks to return (default from settings).
            filter_doc_ids: Optional filter to specific documents.
            prefix: Qdrant collection name prefix (default "kb_").
            context_tag: Optional context tag to filter chunks ("chat" or "reactive").

        Returns:
            RetrievalResult with chunks, formatted context, and pipeline metrics.
        """
        if top_k is None:
            top_k = settings.RAG_RERANK_TOP_K

        metrics = RetrievalMetrics(query=query)

        # ── Stage 1: Query Enhancement ──
        with StageTimer("enhance", metrics) as stage:
            enhanced_queries = await self._query_enhancer.enhance(query)
            stage.input_count = 1
            stage.output_count = len(enhanced_queries)
            metrics.enhanced_queries_count = len(enhanced_queries)

        # ── Stage 2: Embed + Retrieve (per query, then deduplicate) ──
        all_chunks: dict[str, dict] = {}  # id → chunk (dedup by point ID)

        with StageTimer("retrieve", metrics) as stage:
            stage.input_count = len(enhanced_queries)

            # 1. Batch generate dense embeddings (vectorized model inference)
            dense_embs = await self._embed_texts(enhanced_queries)

            # 2. Batch generate sparse embeddings (if hybrid enabled)
            sparse_embs = []
            if self._sparse_embed_texts is not None:
                sparse_embs = await self._sparse_embed_texts(enhanced_queries)

            # 3. Perform Qdrant hybrid searches concurrently via asyncio.gather
            search_tasks = []
            for i, eq in enumerate(enhanced_queries):
                dense_emb = dense_embs[i]
                sparse_q = sparse_embs[i] if sparse_embs else None
                search_tasks.append(
                    self._vector_repo.search_chunks(
                        knowledge_base_id=knowledge_base_id,
                        query_embedding=dense_emb,
                        top_k=settings.RAG_PREFETCH_LIMIT,
                        filter_doc_ids=filter_doc_ids,
                        sparse_query=sparse_q,
                        prefetch_limit=settings.RAG_PREFETCH_LIMIT,
                        prefix=prefix,
                        context=context_tag,
                    )
                )

            results_list = await asyncio.gather(*search_tasks)

            # 4. Deduplicate across all query variations by point ID, keeping highest score
            for results in results_list:
                for chunk in results:
                    cid = chunk["id"]
                    if cid not in all_chunks or chunk.get("score", 0) > all_chunks[cid].get("score", 0):
                        all_chunks[cid] = chunk

            deduplicated = list(all_chunks.values())
            stage.output_count = len(deduplicated)
            if deduplicated:
                scores = [c.get("score", 0) for c in deduplicated]
                stage.best_score = max(scores)
                stage.worst_score = min(scores)

        # ── Stage 3: Rerank ──
        with StageTimer("rerank", metrics) as stage:
            stage.input_count = len(deduplicated)
            reranked = await self._reranker.rerank(query, deduplicated, top_k=top_k)
            stage.output_count = len(reranked)
            if reranked:
                stage.best_score = reranked[0].get("rerank_score", 0)
                stage.worst_score = reranked[-1].get("rerank_score", 0) if reranked else 0

        # ── Stage 4: Format Context ──
        with StageTimer("format", metrics) as stage:
            stage.input_count = len(reranked)
            formatted_context = self._format_context(reranked, query)
            stage.output_count = 1 if formatted_context else 0

        metrics.final_chunk_count = len(reranked)
        metrics.hit = formatted_context is not None
        metrics.log_summary()

        return RetrievalResult(chunks=reranked, context=formatted_context, metrics=metrics)

    @staticmethod
    def _format_context(
        results: list[dict],
        query: str,
        min_score: float | None = None,
    ) -> str | None:
        """Format retrieved chunks into an XML-structured context for the LLM.

        Includes source citations with rank, score, rerank_score, filename,
        and page number for full traceability.
        """
        if min_score is None:
            min_score = settings.RAG_MIN_RELEVANCE_SCORE

        # Use rerank_score if available, otherwise fall back to retrieval score
        def _effective_score(r: dict) -> float:
            return r.get("rerank_score", r.get("score", 0.0))

        filtered = [r for r in results if _effective_score(r) >= min_score]
        if not filtered:
            logger.debug(
                "All RAG chunks scored below %.2f; dropping context", min_score
            )
            return None

        filtered.sort(key=_effective_score, reverse=True)

        sources: list[str] = []
        for i, r in enumerate(filtered, start=1):
            filename = r.get("filename") or "unknown"
            page = r.get("page_number")
            score = r.get("score", 0.0)
            rerank_score = r.get("rerank_score")

            attrs = f'rank="{i}" doc="{filename}" score="{score:.3f}"'
            if rerank_score is not None:
                attrs += f' rerank_score="{rerank_score:.4f}"'
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
