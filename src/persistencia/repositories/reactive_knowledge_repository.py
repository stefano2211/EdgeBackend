"""Reactive KnowledgeBase repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.reactive_knowledge_base import ReactiveKnowledgeBase
from src.persistencia.repositories.base_repository import BaseRepository


class ReactiveKnowledgeRepository(BaseRepository[ReactiveKnowledgeBase]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReactiveKnowledgeBase)

    async def list_by_user(self, user_id: int) -> list[ReactiveKnowledgeBase]:
        stmt = (
            select(ReactiveKnowledgeBase)
            .where(ReactiveKnowledgeBase.user_id == user_id)
            .order_by(ReactiveKnowledgeBase.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id_for_user(self, kb_id: int, user_id: int) -> ReactiveKnowledgeBase | None:
        stmt = select(ReactiveKnowledgeBase).where(
            ReactiveKnowledgeBase.id == kb_id,
            ReactiveKnowledgeBase.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
