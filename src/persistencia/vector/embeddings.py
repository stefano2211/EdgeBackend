"""Embedding utility using sentence-transformers as the default backend."""

import asyncio
from typing import List
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from src.core.config import settings


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(settings.EMBEDDINGS_MODEL)


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Compute embeddings asynchronously in a thread pool."""
    model = _get_model()
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(None, model.encode, texts)
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    model = _get_model()
    return model.get_sentence_embedding_dimension()
