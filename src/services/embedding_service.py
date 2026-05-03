"""Async embedding service using sentence-transformers.

Optimised for:
- Thread-pool offloading so the event loop never blocks.
- Automatic batching for very large inputs (prevents memory spikes).
- Model singleton (loaded once per process).
"""

import asyncio
from functools import lru_cache, partial

import numpy as np
from sentence_transformers import SentenceTransformer

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2

# Cap batch size for automatic chunking to avoid OOM on very long inputs
_MAX_BATCH_SIZE = 64


def _load_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDINGS_MODEL)
        _model = SentenceTransformer(settings.EMBEDDINGS_MODEL)
    return _model


def _encode_batch(
    model: SentenceTransformer,
    texts: list[str],
    *,
    batch_size: int,
    normalize: bool,
) -> np.ndarray:
    """Synchronous wrapper for model.encode (runs in thread pool)."""
    return model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )


async def embed_texts(
    texts: list[str],
    batch_size: int = 64,
    normalize: bool = True,
) -> list[list[float]]:
    """
    Embed a list of texts asynchronously (non-blocking via thread pool).

    Large inputs are transparently split into sub-batches so memory stays
    bounded regardless of input length.

    Args:
        texts: Input strings to embed.
        batch_size: Encoder batch size (capped at 64 internally).
        normalize: True improves cosine-similarity search in Qdrant.
    """
    if not texts:
        return []

    model = _load_model()
    loop = asyncio.get_running_loop()
    batch_size = min(batch_size, _MAX_BATCH_SIZE)

    # For small inputs a single encode call is fastest.
    if len(texts) <= batch_size * 4:
        func = partial(_encode_batch, model, texts, batch_size=batch_size, normalize=normalize)
        embeddings = await loop.run_in_executor(None, func)
        return embeddings.tolist()

    # Large inputs: split into sub-batches and encode sequentially
    # (sentence-transformers is CPU-bound; parallelism hurts more than helps).
    all_embeddings: list[np.ndarray] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        func = partial(_encode_batch, model, batch, batch_size=len(batch), normalize=normalize)
        emb = await loop.run_in_executor(None, func)
        all_embeddings.append(emb)

    stacked = np.vstack(all_embeddings)
    return stacked.tolist()


@lru_cache(maxsize=1024)
def _cached_embed_sync(text: str) -> tuple[float, ...]:
    """LRU-cached synchronous single-text embedding (for repeated queries)."""
    model = _load_model()
    emb = model.encode([text], batch_size=1, show_progress_bar=False, normalize_embeddings=True)
    return tuple(emb[0].tolist())


async def embed_query(text: str, *, use_cache: bool = True) -> list[float]:
    """Embed a single query text. Uses LRU cache when enabled."""
    if use_cache:
        loop = asyncio.get_running_loop()
        cached = await loop.run_in_executor(None, _cached_embed_sync, text)
        return list(cached)

    embeddings = await embed_texts([text], batch_size=1)
    return embeddings[0]
