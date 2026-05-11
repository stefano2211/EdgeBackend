"""Business logic for reactive user configuration.

Reads directly from reactive tables (ReactiveKnowledgeBase, ReactiveToolConfig)
using their native is_enabled fields — no junction tables required.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.repositories.reactive_knowledge_repository import ReactiveKnowledgeRepository
from src.persistencia.repositories.reactive_tool_repository import ReactiveToolRepository

logger = logging.getLogger(__name__)


class ReactiveConfigService:
    """Facade for reactive configuration management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tool_repo = ReactiveToolRepository(session)
        self._kb_repo = ReactiveKnowledgeRepository(session)

    async def list_tools(self, user_id: int) -> list[dict]:
        """Return all reactive tools for the user."""
        tools = await self._tool_repo.list()
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "is_enabled": t.is_enabled,
                "user_id": t.user_id,
                "source_name": t.source.name if hasattr(t, 'source') and t.source else None,
            }
            for t in tools
            if t.user_id == user_id
        ]

    async def toggle_tool(self, user_id: int, tool_id: int, enabled: bool) -> None:
        """Enable or disable a reactive tool."""
        tool = await self._tool_repo.get_by_id(tool_id)
        if tool and tool.user_id == user_id:
            tool.is_enabled = enabled
            await self._session.commit()
            logger.info(
                "User %s %s reactive tool %s",
                user_id,
                "enabled" if enabled else "disabled",
                tool_id,
            )

    async def list_knowledge_bases(self, user_id: int) -> list[dict]:
        """Return all reactive KBs for the user."""
        kbs = await self._kb_repo.list_by_user(user_id)
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "is_enabled": kb.is_enabled,
                "document_count": len(kb.documents),
            }
            for kb in kbs
        ]

    async def toggle_knowledge_base(self, user_id: int, kb_id: int, enabled: bool) -> None:
        """Enable or disable a reactive knowledge base."""
        kb = await self._kb_repo.get_by_id_for_user(kb_id, user_id)
        if kb:
            kb.is_enabled = enabled
            await self._session.commit()
            logger.info(
                "User %s %s reactive KB %s",
                user_id,
                "enabled" if enabled else "disabled",
                kb_id,
            )

    async def get_enabled_tools(self, user_id: int) -> list[int]:
        """Return IDs of reactive tools enabled for the user."""
        tools = await self._tool_repo.list_enabled_by_user(user_id)
        return [t.id for t in tools]

    async def get_enabled_knowledge_bases(self, user_id: int) -> list[int]:
        """Return IDs of reactive KBs enabled for the user."""
        kbs = await self._kb_repo.list_by_user(user_id)
        return [kb.id for kb in kbs if kb.is_enabled]

    async def has_any_config(self, user_id: int) -> bool:
        """Return True if the user has enabled at least one reactive tool or KB."""
        tools = await self._tool_repo.list_enabled_by_user(user_id)
        kbs = await self._kb_repo.list_by_user(user_id)
        return bool(tools or any(kb.is_enabled for kb in kbs))
