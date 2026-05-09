"""Repository for UserReactiveKnowledgeBase junction table."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.knowledge_base import KnowledgeBase
from src.persistencia.models.user_reactive_kb import UserReactiveKnowledgeBase


class UserReactiveKbRepository:
    """Manages per-user knowledge base enablement for reactive events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_enabled_kbs(self, user_id: int) -> list[KnowledgeBase]:
        """Return all KBs enabled by this user for reactive events."""
        stmt = (
            select(KnowledgeBase)
            .join(
                UserReactiveKnowledgeBase,
                UserReactiveKnowledgeBase.knowledge_base_id == KnowledgeBase.id,
            )
            .where(
                UserReactiveKnowledgeBase.user_id == user_id,
                UserReactiveKnowledgeBase.is_enabled == True,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_with_status(self, user_id: int) -> list[dict]:
        """Return ALL KBs with an `is_enabled` flag for the given user."""
        stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
        kbs_result = await self._session.execute(stmt)
        kbs = list(kbs_result.scalars().all())

        prefs_stmt = select(UserReactiveKnowledgeBase).where(
            UserReactiveKnowledgeBase.user_id == user_id
        )
        prefs_result = await self._session.execute(prefs_stmt)
        prefs = {p.knowledge_base_id: p.is_enabled for p in prefs_result.scalars().all()}

        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "document_count": len(kb.documents),
                "is_enabled": prefs.get(kb.id, False),
            }
            for kb in kbs
        ]

    async def set_enabled(self, user_id: int, kb_id: int, enabled: bool) -> None:
        """Upsert the enabled state for a user-KB pair."""
        stmt = (
            pg_insert(UserReactiveKnowledgeBase)
            .values(
                user_id=user_id,
                knowledge_base_id=kb_id,
                is_enabled=enabled,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "knowledge_base_id"],
                set_={"is_enabled": enabled},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
