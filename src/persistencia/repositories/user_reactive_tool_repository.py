"""Repository for UserReactiveTool junction table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.tool_config import ToolConfig
from src.persistencia.models.user_reactive_tool import UserReactiveTool


class UserReactiveToolRepository:
    """Manages per-user tool enablement for reactive events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_enabled_tools(self, user_id: int) -> list[ToolConfig]:
        """Return all tools enabled by this user for reactive events."""
        stmt = (
            select(ToolConfig)
            .join(UserReactiveTool, UserReactiveTool.tool_config_id == ToolConfig.id)
            .where(
                UserReactiveTool.user_id == user_id,
                UserReactiveTool.is_enabled == True,
                ToolConfig.is_enabled == True,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_status(self, user_id: int) -> list[dict]:
        """Return ALL tools with an `is_enabled` flag for the given user."""
        stmt = select(ToolConfig).where(ToolConfig.is_enabled == True)
        tools_result = await self._session.execute(stmt)
        tools = list(tools_result.scalars().all())

        prefs_stmt = select(UserReactiveTool).where(UserReactiveTool.user_id == user_id)
        prefs_result = await self._session.execute(prefs_stmt)
        prefs = {p.tool_config_id: p.is_enabled for p in prefs_result.scalars().all()}

        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "source_name": t.source.name if t.source else None,
                "is_enabled": prefs.get(t.id, False),
            }
            for t in tools
        ]

    async def set_enabled(self, user_id: int, tool_config_id: int, enabled: bool) -> None:
        """Upsert the enabled state for a user-tool pair."""
        stmt = (
            pg_insert(UserReactiveTool)
            .values(
                user_id=user_id,
                tool_config_id=tool_config_id,
                is_enabled=enabled,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "tool_config_id"],
                set_={"is_enabled": enabled},
            )
        )
        await self._session.execute(stmt)
