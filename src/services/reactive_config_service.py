"""Business logic for reactive user configuration.

Reads directly from unified KnowledgeBase table using is_enabled_reactive field,
plus ReactiveToolConfig for reactive tools.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.repositories.knowledge_repository import KnowledgeRepository
from src.persistencia.repositories.reactive_tool_repository import ReactiveToolRepository

logger = logging.getLogger(__name__)


class ReactiveConfigService:
    """Facade for reactive configuration management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._tool_repo = ReactiveToolRepository(session)
        self._kb_repo = KnowledgeRepository(session)

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
        """Return all reactive-enabled KBs for the user."""
        kbs = await self._kb_repo.list_enabled_for_reactive(user_id)
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "is_enabled": kb.is_enabled_reactive,
                "document_count": len(kb.documents),
            }
            for kb in kbs
        ]

    async def toggle_knowledge_base(self, user_id: int, kb_id: int, enabled: bool) -> None:
        """Enable or disable a reactive knowledge base."""
        kb = await self._kb_repo.get_by_id_for_user(kb_id, user_id)
        if kb:
            kb.is_enabled_reactive = enabled
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
        kbs = await self._kb_repo.list_enabled_for_reactive(user_id)
        return [kb.id for kb in kbs]

    async def get_enabled_resources(self, user_id: int) -> dict:
        """Return both IDs and names of enabled reactive tools and KBs."""
        tools = await self._tool_repo.list_enabled_by_user(user_id)
        kbs = await self._kb_repo.list_enabled_for_reactive(user_id)
        
        return {
            "tool_ids": [t.id for t in tools],
            "tool_names": [t.name for t in tools],
            "kb_ids": [kb.id for kb in kbs],
            "kb_names": [kb.name for kb in kbs],
        }

    async def has_any_config(self, user_id: int) -> bool:
        """Return True if the user has enabled at least one reactive tool or KB."""
        res = await self.get_enabled_resources(user_id)
        return bool(res["tool_ids"] or res["kb_ids"])
