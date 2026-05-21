"""Base MCP source service — shared logic between chat and reactive contexts."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.exceptions import NotFoundError
from src.core.logging import logging
from src.persistencia.models.base import Base
from src.persistencia.repositories.base_repository import BaseRepository
from src.services.base_crud_service import BaseCRUDService
from src.services._helpers import apply_patch, commit_and_refresh
from src.services.mcp_service import MCPService

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

    async def sync_source_tools(
        self,
        source_id: int,
        *,
        method: str = "GET",
        is_resource: bool = False,
    ) -> dict:
        """Connect to an MCP source, discover tools, and auto-register them.

        Uses batch add + single commit to avoid per-tool flush overhead.

        Returns:
            {"tools_discovered": int, "tools_added": int}
        """
        source = await self.get(source_id)
        mcp_service = MCPService()

        discovered_tools = await mcp_service.discover_tools(
            base_url=source.url,
            is_stdio=(source.type == "stdio"),
            method=method,
            is_resource=is_resource,
        )

        existing_tools = await self.tool_repo.list_by_source(source_id)
        existing_names = {t.name for t in existing_tools}

        added = 0
        new_tools: list[TTool] = []
        for tool_def in discovered_tools:
            if not isinstance(tool_def, dict):
                logger.warning(
                    "[MCP Sync] Skipping non-dict discovery result for source_id=%s: %r",
                    source_id,
                    tool_def,
                )
                continue
            name = tool_def.get("name")
            if not name or name in existing_names:
                continue

            tool = self.tool_model_class(
                name=name,
                description=tool_def.get("description") or "",
                parameter_schema=tool_def.get("parameter_schema")
                or tool_def.get("inputSchema")
                or {},
                config=tool_def.get("config", {"transport": source.type, "url": source.url}),
                source_id=source_id,
                is_enabled=True,
            )
            # Reactive models require a user_id — inject it when present
            if hasattr(tool, "user_id") and hasattr(source, "user_id"):
                tool.user_id = source.user_id

            new_tools.append(tool)
            added += 1

        if new_tools:
            for tool in new_tools:
                self.session.add(tool)
            await self.session.commit()

        return {"tools_discovered": len(discovered_tools), "tools_added": added}

    async def update(self, obj_id: int, data: TSourceUpdate) -> TSource:
        """Update an MCP source and invalidate its URL cache."""
        obj = await super().update(obj_id, data)
        # Invalidate per-context cache so resolved URLs are refreshed
        try:
            from src.ia.tools.unified.mcp import invalidate_mcp_cache

            invalidate_mcp_cache(self._cache_context, obj_id)
        except Exception:
            logger.exception("Failed to invalidate MCP cache for source_id=%s", obj_id)
        return obj

    async def delete(self, obj_id: int) -> None:
        """Delete an MCP source and invalidate its URL cache."""
        try:
            from src.ia.tools.unified.mcp import invalidate_mcp_cache

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
