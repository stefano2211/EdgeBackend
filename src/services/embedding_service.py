"""Async embedding service using sentence-transformers.

Layer: services (business logic / domain orchestration)
"""

import asyncio
from functools import partial

from sentence_transformers import SentenceTransformer

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None

EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2


def _load_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDINGS_MODEL)
        _model = SentenceTransformer(settings.EMBEDDINGS_MODEL)
    return _model


async def embed_texts(
    texts: list[str],
    batch_size: int = 64,
    normalize: bool = True,
) -> list[list[float]]:
    """
    Embed a list of texts asynchronously (non-blocking via thread pool).

    Args:
        texts: Input strings to embed.
        batch_size: 64 is optimal throughput for all-MiniLM-L6-v2 on CPU/GPU.
        normalize: True improves cosine-similarity search in Qdrant.
    """
    model = _load_model()
    loop = asyncio.get_running_loop()
    func = partial(
        model.encode,
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )
    embeddings = await loop.run_in_executor(None, func)
    return embeddings.tolist()


async def embed_query(text: str) -> list[float]:
    """Embed a single query text (batch_size=1)."""
    embeddings = await embed_texts([text], batch_size=1)
    return embeddings[0]
