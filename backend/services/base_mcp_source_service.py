"""Base MCP source service — shared logic between chat and reactive contexts."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal
from backend.core.exceptions import NotFoundError
from backend.core.logging import logging
from backend.persistencia.models.base import Base
from backend.persistencia.repositories.base_repository import BaseRepository
from backend.services.base_crud_service import BaseCRUDService
from backend.services._helpers import apply_patch, commit_and_refresh
from backend.services.mcp_service import MCPService

logger = logging.getLogger(__name__)

TSource = TypeVar("TSource", bound=Base)
TSourceCreate = TypeVar("TSourceCreate", bound=BaseModel)
TSourceUpdate = TypeVar("TSourceUpdate", bound=BaseModel)
TTool = TypeVar("TTool", bound=Base)


class BaseMCPSourceService(
    BaseCRUDService[TSource, TSourceCreate, TSourceUpdate],
    Generic[TSource, TSourceCreate, TSourceUpdate, TTool],
):
    """Shared CRUD + sync logic for MCP sources (chat or reactive)."""

    tool_model_class: type[TTool]
    tool_repo_class: type[BaseRepository[TTool]]
    _cache_context: str  # "chat" or "reactive"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.tool_repo = self.tool_repo_class(session)

    async def update(self, obj_id: int, data: TSourceUpdate) -> TSource:
        """Update an MCP source and invalidate its URL cache."""
        obj = await super().update(obj_id, data)
        # Invalidate per-context cache so resolved URLs are refreshed
        try:
            from backend.ia.tools.unified.mcp import invalidate_mcp_cache

            invalidate_mcp_cache(self._cache_context, obj_id)
        except Exception:
            logger.exception("Failed to invalidate MCP cache for source_id=%s", obj_id)
        return obj

    async def delete(self, obj_id: int) -> None:
        """Delete an MCP source and invalidate its URL cache."""
        try:
            from backend.ia.tools.unified.mcp import invalidate_mcp_cache

            invalidate_mcp_cache(self._cache_context, obj_id)
        except Exception:
            logger.exception("Failed to invalidate MCP cache for source_id=%s", obj_id)
        await super().delete(obj_id)

    async def create_for_user(
        self, data: TSourceCreate, user_id: int
    ) -> TSource:
        """Create a source scoped to a specific user (for reactive contexts)."""
        obj = self.model_class(**data.model_dump(), user_id=user_id)
        await self.repo.create(obj)
        await commit_and_refresh(self.session, obj)
        return obj
