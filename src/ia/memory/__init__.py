"""Production memory layer with resilient fallback chain.

Priority:
1. langgraph-redis (AsyncRedisSaver + AsyncRedisStore) — requires `pip install langgraph-redis`
2. langgraph.checkpoint.memory.MemorySaver + langgraph.store.memory.InMemoryStore

Initialized once at FastAPI lifespan startup.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.embeddings import Embeddings

from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2


class SentenceTransformerEmbeddings(Embeddings):
    """LangChain-compatible wrapper around sentence-transformers."""

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer
        name = model_name or settings.EMBEDDINGS_MODEL
        logger.info("Loading embedding model for store: %s", name)
        self._model = SentenceTransformer(name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import numpy as np
        embeddings = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        if isinstance(embeddings, np.ndarray):
            return embeddings.tolist()
        return embeddings  # type: ignore[return-value]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# ── Singletons — populated by init_memory() ──
_checkpointer: Any | None = None
_store: Any | None = None


async def init_memory() -> None:
    """Initialize checkpointer and store with fallback chain.

    Call once in FastAPI lifespan startup.
    """
    global _checkpointer, _store

    # ── 1. Checkpointer (Redis → Memory fallback) ──
    try:
        from langgraph_redis.checkpoint import AsyncRedisSaver
        _checkpointer = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
        await _checkpointer.asetup()
        logger.info("Redis checkpointer ready: %s", settings.REDIS_URL)
    except Exception:
        logger.warning(
            "Redis checkpointer unavailable (langgraph-redis not installed or Redis down). "
            "Falling back to in-memory MemorySaver."
        )
        from langgraph.checkpoint.memory import MemorySaver
        _checkpointer = MemorySaver()
        logger.info("In-memory checkpointer ready")

    # ── 2. Store (Redis → InMemory fallback) ──
    try:
        from langgraph_redis.store import AsyncRedisStore
        embeddings = SentenceTransformerEmbeddings()

        def _init_redis_store():
            return AsyncRedisStore.from_conn_string(
                settings.REDIS_URL,
                index_config={
                    "dims": EMBEDDING_DIMENSION,
                    "embed": embeddings,
                },
            )

        loop = asyncio.get_running_loop()
        _store = await loop.run_in_executor(None, _init_redis_store)
        logger.info("Redis store ready with semantic search (dims=%d)", EMBEDDING_DIMENSION)
    except Exception:
        logger.warning(
            "Redis store unavailable (langgraph-redis not installed or Redis down). "
            "Falling back to in-memory InMemoryStore (no persistence)."
        )
        from langgraph.store.memory import InMemoryStore
        _store = InMemoryStore()
        logger.info("In-memory store ready")


def get_checkpointer() -> Any:
    if _checkpointer is None:
        raise RuntimeError("Memory not initialized. Call init_memory() first.")
    return _checkpointer


def get_store() -> Any:
    if _store is None:
        raise RuntimeError("Memory not initialized. Call init_memory() first.")
    return _store


# ── Async helpers for the store (wrap sync store in thread pool) ──

async def save_user_memory(
    user_id: str,
    key: str,
    text: str,
    metadata: dict | None = None,
) -> None:
    """Save a user-scoped memory to the store."""
    store = get_store()
    value: dict = {"text": text, **(metadata or {})}

    # AsyncRedisStore has async put; InMemoryStore is sync
    if asyncio.iscoroutinefunction(store.put):
        await store.put(
            namespace=(user_id, "memories"),
            key=key,
            value=value,
        )
        return

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: store.put(
            namespace=(user_id, "memories"),
            key=key,
            value=value,
        ),
    )


async def search_user_memories(
    user_id: str,
    query: str,
    limit: int = 3,
) -> list[dict]:
    """Semantic search over user's long-term memories."""
    store = get_store()

    # AsyncRedisStore has async search; InMemoryStore is sync
    if asyncio.iscoroutinefunction(store.search):
        results = await store.search(
            namespace=(user_id, "memories"),
            query=query,
            limit=limit,
        )
    else:
        loop = asyncio.get_running_loop()

        def _search():
            return store.search(
                namespace=(user_id, "memories"),
                query=query,
                limit=limit,
            )

        results = await loop.run_in_executor(None, _search)

    return [
        {
            "key": r.key,
            "text": r.value.get("text", ""),
            "score": getattr(r, "score", None),
            **{k: v for k, v in r.value.items() if k != "text"},
        }
        for r in results
    ]
