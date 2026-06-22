"""Shared session provider for IA tools.

Tools that need database access should use get_session() as an async context manager.
This centralizes session creation and makes it easier to swap in pooled or test sessions.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for tool execution.

    Defaults to AsyncSessionLocal. Override this for testing or batching.
    """
    async with AsyncSessionLocal() as session:
        yield session
