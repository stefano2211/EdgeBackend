"""Async sparse (BM25) embedding service using fastembed.

Generates sparse vectors for hybrid search in Qdrant.
Paired with dense embeddings from embedding_service.py to enable
Reciprocal Rank Fusion (RRF) for optimal retrieval quality.

Optimised for:
- Thread-pool offloading so the event loop never blocks.
- Model singleton (loaded once per process).
- Batch encoding for large document ingestion.
"""

from __future__ import annotations

import asyncio
from functools import partial

from backend.core.config import settings
from backend.core.logging import logging
from backend.persistencia.vector.vector_store_port import SparseVector

logger = logging.getLogger(__name__)

_sparse_model = None


def _load_sparse_model():
    """Load the sparse embedding model (singleton)."""
    global _sparse_model
    if _sparse_model is None:
        from fastembed import SparseTextEmbedding

        logger.info("Loading sparse embedding model: %s", settings.SPARSE_EMBEDDINGS_MODEL)
        _sparse_model = SparseTextEmbedding(model_name=settings.SPARSE_EMBEDDINGS_MODEL)
    return _sparse_model


def _encode_sparse_batch(model, texts: list[str]) -> list[SparseVector]:
    """Synchronous sparse encoding (runs in thread pool)."""
    results = list(model.embed(texts))
    return [
        SparseVector(
            indices=r.indices.tolist(),
            values=r.values.tolist(),
        )
        for r in results
    ]


async def embed_sparse_texts(texts: list[str]) -> list[SparseVector]:
    """Embed a list of texts as sparse BM25 vectors asynchronously.

    Each sparse vector contains only the non-zero dimensions,
    representing term frequencies weighted by IDF.

    Args:
        texts: Input strings to embed.

    Returns:
        List of SparseVector with indices and values for each text.
    """
    if not texts:
        return []

    model = _load_sparse_model()
    loop = asyncio.get_running_loop()
    func = partial(_encode_sparse_batch, model, texts)
    return await loop.run_in_executor(None, func)


async def embed_sparse_query(text: str) -> SparseVector:
    """Embed a single query text as a sparse BM25 vector."""
    results = await embed_sparse_texts([text])
    return results[0]
