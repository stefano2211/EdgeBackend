"""Business logic for reactive user configuration."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.repositories.user_reactive_tool_repository import UserReactiveToolRepository
from src.persistencia.repositories.user_reactive_kb_repository import UserReactiveKbRepository

logger = logging.getLogger(__name__)


class ReactiveConfigService:
    """Facade for reactive configuration management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tool_repo = UserReactiveToolRepository(session)
        self._kb_repo = UserReactiveKbRepository(session)

    async def list_tools(self, user_id: int) -> list[dict]:
        """Return all tools with user's reactive enablement status."""
        return await self._tool_repo.list_with_status(user_id)

    async def toggle_tool(self, user_id: int, tool_id: int, enabled: bool) -> None:
        """Enable or disable a tool for reactive events."""
        await self._tool_repo.set_enabled(user_id, tool_id, enabled)
        await self._session.commit()
        logger.info(
            "User %s %s tool %s for reactive",
            user_id,
            "enabled" if enabled else "disabled",
            tool_id,
        )

    async def list_knowledge_bases(self, user_id: int) -> list[dict]:
        """Return all KBs with user's reactive enablement status."""
        return await self._kb_repo.list_with_status(user_id)

    async def toggle_knowledge_base(self, user_id: int, kb_id: int, enabled: bool) -> None:
        """Enable or disable a KB for reactive events."""
        await self._kb_repo.set_enabled(user_id, kb_id, enabled)
        await self._session.commit()
        logger.info(
            "User %s %s KB %s for reactive",
            user_id,
            "enabled" if enabled else "disabled",
            kb_id,
        )

    async def get_enabled_tools(self, user_id: int) -> list[int]:
        """Return IDs of tools enabled for reactive events (used by orchestrator)."""
        tools = await self._tool_repo.get_enabled_tools(user_id)
        return [t.id for t in tools]

    async def get_enabled_knowledge_bases(self, user_id: int) -> list[int]:
        """Return IDs of KBs enabled for reactive events (used by orchestrator)."""
        kbs = await self._kb_repo.get_enabled_kbs(user_id)
        return [kb.id for kb in kbs]

    async def has_any_config(self, user_id: int) -> bool:
        """Return True if the user has enabled at least one tool or one KB."""
        tools = await self._tool_repo.get_enabled_tools(user_id)
        kbs = await self._kb_repo.get_enabled_kbs(user_id)
        return bool(tools or kbs)
