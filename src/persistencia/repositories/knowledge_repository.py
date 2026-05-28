"""KnowledgeBase repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.knowledge_base import KnowledgeBase
from src.persistencia.repositories.base_repository import BaseRepository


class KnowledgeRepository(BaseRepository[KnowledgeBase]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KnowledgeBase)

    async def list_by_user(self, user_id: int) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id_for_user(self, kb_id: int, user_id: int) -> KnowledgeBase | None:
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_enabled_for_chat(self, user_id: int) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id, KnowledgeBase.is_enabled_chat.is_(True))
            .order_by(KnowledgeBase.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_enabled_for_reactive(self, user_id: int) -> list[KnowledgeBase]:
        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id, KnowledgeBase.is_enabled_reactive.is_(True))
            .order_by(KnowledgeBase.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
