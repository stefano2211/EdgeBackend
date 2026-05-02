"""Conversation repository with thread_id and user lookups."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.conversation import Conversation
from src.persistencia.repositories.base_repository import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversation)

    async def get_by_thread_id(self, thread_id: str) -> Conversation | None:
        stmt = select(Conversation).where(Conversation.thread_id == thread_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int, include_archived: bool = False) -> list[Conversation]:
        stmt = select(Conversation).where(Conversation.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(Conversation.is_archived == False)
        stmt = stmt.order_by(Conversation.updated_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def archive(self, thread_id: str, archive: bool = True) -> Conversation | None:
        conv = await self.get_by_thread_id(thread_id)
        if conv:
            conv.is_archived = archive
            await self.session.flush()
        return conv
