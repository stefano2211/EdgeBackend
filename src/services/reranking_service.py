"""Cross-Encoder reranking service for precision-optimized RAG.

Reranking is the highest-leverage optimization for RAG precision.
Unlike bi-encoders (which encode query and document separately),
a cross-encoder processes query+document together in a single pass,
capturing token-level interactions (negation, pronoun resolution,
implicit relationships) that bi-encoders miss.

Pipeline: Retrieve 50 candidates (hybrid) → Rerank → Return top 5.

Optimised for:
- Thread-pool offloading (CPU-bound inference).
- Model singleton (loaded once per process).
- Batch prediction for efficiency.
- Multilingual support (BGE-reranker-v2-m3 handles ES/EN/PT).
"""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Protocol

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)

_reranker_model = None


class RerankerPort(Protocol):
    """Abstract reranker for dependency inversion (DIP)."""

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        ...


def _load_reranker():
    """Load the cross-encoder model (singleton)."""
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers import CrossEncoder

        logger.info("Loading reranker model: %s", settings.RERANKER_MODEL)
        _reranker_model = CrossEncoder(settings.RERANKER_MODEL, device="cpu")
    return _reranker_model


def _predict_sync(model, pairs: list[list[str]]) -> list[float]:
    """Synchronous cross-encoder prediction (runs in thread pool)."""
    scores = model.predict(pairs, show_progress_bar=False)
    return [float(s) for s in scores]


class CrossEncoderReranker:
    """Production reranker using BGE cross-encoder.

    Processes query-document pairs together for high-precision relevance
    scoring. Should be applied after initial retrieval (hybrid search)
    to filter and reorder candidates.
    """

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """Rerank retrieved chunks by cross-encoder relevance.

        Args:
            query: The user's search query.
            chunks: Retrieved chunks from hybrid search (each has "text" key).
            top_k: Number of top results to return after reranking.

        Returns:
            Top-k chunks sorted by rerank_score (descending), each enriched
            with a "rerank_score" field.
        """
        if not chunks:
            return []

        if len(chunks) <= top_k:
            # No need to rerank if we have fewer chunks than requested
            for chunk in chunks:
                chunk["rerank_score"] = chunk.get("score", 0.0)
            return chunks

        model = _load_reranker()
        pairs = [[query, c["text"]] for c in chunks]

        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(
            None, partial(_predict_sync, model, pairs)
        )

        # Enrich chunks with rerank scores
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = score

        # Sort by rerank_score descending and return top_k
        ranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
        logger.debug(
            "Reranked %d chunks → top %d (best=%.4f, worst=%.4f)",
            len(chunks),
            top_k,
            ranked[0]["rerank_score"] if ranked else 0,
            ranked[min(top_k, len(ranked)) - 1]["rerank_score"] if ranked else 0,
        )
        return ranked[:top_k]


class NoOpReranker:
    """Passthrough reranker that does nothing (for when reranking is disabled)."""

    async def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        for chunk in chunks:
            chunk["rerank_score"] = chunk.get("score", 0.0)
        return chunks[:top_k]


def get_reranker() -> CrossEncoderReranker | NoOpReranker:
    """Factory: return the appropriate reranker based on settings."""
    if settings.RERANKER_ENABLED:
        return CrossEncoderReranker()
    return NoOpReranker()
