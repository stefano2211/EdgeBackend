"""Memory layer for DeepAgents — LangGraph checkpoints and store.

Provides:
  - init_memory(): initialize Redis checkpointer + Postgres store
  - get_checkpointer(): return AsyncRedisSaver instance
  - get_store(): return PostgresStore instance

Graceful fallback: if Redis/Postgres unavailable, returns None
(so DeepAgents uses in-memory defaults).
"""

from __future__ import annotations

import logging

from backend.core.config import settings

logger = logging.getLogger(__name__)

_checkpointer = None
_store = None


async def init_memory() -> None:
    """Initialize Redis checkpointer and Postgres store if available."""
    global _checkpointer, _store

    # Try Redis checkpointer
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        import redis.asyncio as redis

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Quick health check
        await redis_client.ping()
        _checkpointer = AsyncRedisSaver(conn=redis_client)
        logger.info("Redis checkpointer initialized")
    except Exception as exc:
        logger.warning("Redis checkpointer not available: %s", exc)
        _checkpointer = None

    # Try Postgres store
    try:
        from langgraph.store.postgres import PostgresStore
        from psycopg import Connection
        from psycopg_pool import ConnectionPool

        # Build connection pool from DATABASE_URL
        # Note: psycopg requires a sync pool for PostgresStore
        pool = ConnectionPool(conninfo=settings.DATABASE_URL.replace("+asyncpg", ""))
        _store = PostgresStore(pool=pool)
        logger.info("Postgres store initialized")
    except Exception as exc:
        logger.warning("Postgres store not available: %s", exc)
        _store = None


def get_checkpointer():
    """Return the initialized checkpointer, or raise RuntimeError."""
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized. Call init_memory() first.")
    return _checkpointer


def get_store():
    """Return the initialized store, or raise RuntimeError."""
    if _store is None:
        raise RuntimeError("Store not initialized. Call init_memory() first.")
    return _store
