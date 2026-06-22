"""Message repository with conversation lookups."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.message import Message
from backend.infrastructure.persistence.base_repository import BaseRepository


class MessageRepository(BaseRepository[Message]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Message)

    async def list_by_conversation(self, conversation_id: int) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        reasoning_content: str | None = None,
        meta: dict | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            reasoning_content=reasoning_content,
            meta=meta,
        )
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg
