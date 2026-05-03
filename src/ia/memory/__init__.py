"""Production memory layer: Redis Checkpointer + Redis Store.

- Redis Checkpointer (AsyncRedisSaver): fast thread-level persistence for
  conversation checkpoints. Enables pause/resume, crash recovery, HITL.
- Redis Store (RedisStore): durable long-term memory with semantic search.
  User-scoped namespaces isolate memories per tenant.

Note: PostgreSQL Store (PostgresStore) is not yet available as a pip package.
We use Redis for both checkpoint and store — both support semantic search
and share the same Redis instance.

Initialized once at FastAPI lifespan startup.
"""

import asyncio

from langchain_core.embeddings import Embeddings
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.store.redis import RedisStore

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
_checkpointer: AsyncRedisSaver | None = None
_store: RedisStore | None = None


async def init_memory() -> None:
    """Initialize Redis checkpointer and Redis store.

    Call once in FastAPI lifespan startup.
    """
    global _checkpointer, _store

    # ── 1. Redis Checkpointer ──
    _checkpointer = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
    await _checkpointer.asetup()
    logger.info("Redis checkpointer ready: %s", settings.REDIS_URL)

    # ── 2. Redis Store with semantic search ──
    embeddings = SentenceTransformerEmbeddings()

    # RedisStore is sync — initialize in thread pool
    def _init_store() -> RedisStore:
        store = RedisStore.from_conn_string(
            settings.REDIS_URL,
            index_config={
                "dims": EMBEDDING_DIMENSION,
                "embed": embeddings,
            },
        )
        return store

    loop = asyncio.get_running_loop()
    _store = await loop.run_in_executor(None, _init_store)
    logger.info("Redis store ready with semantic search (dims=%d)", EMBEDDING_DIMENSION)


def get_checkpointer() -> AsyncRedisSaver:
    if _checkpointer is None:
        raise RuntimeError("Memory not initialized. Call init_memory() first.")
    return _checkpointer


def get_store() -> RedisStore:
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
    """Save a user-scoped memory to the Redis store."""
    store = get_store()
    value: dict = {"text": text, **(metadata or {})}
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
