"""Conversation domain service — CRUD for conversations."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.conversation import Conversation
from backend.infrastructure.persistence.conversation_repository import ConversationRepository


class ConversationService:
    """Handles conversation lifecycle: creation, listing, archiving, deletion."""

    def __init__(
        self,
        session: AsyncSession,
        repo: ConversationRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repo or ConversationRepository(session)

    async def get_or_create_conversation(
        self, thread_id: str | None, user_id: int, title: str = "New Chat"
    ) -> Conversation:
        if thread_id:
            conv = await self.repo.get_by_thread_id(thread_id)
            if conv and conv.user_id == user_id:
                return conv
        conv = Conversation(user_id=user_id, title=title)
        await self.repo.create(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def list_conversations(
        self, user_id: int, include_archived: bool = False
    ) -> list[Conversation]:
        return await self.repo.list_by_user(user_id, include_archived)

    async def archive_conversation(
        self, thread_id: str, user_id: int, archive: bool = True
    ) -> Conversation | None:
        conv = await self.repo.get_by_thread_id(thread_id)
        if not conv or conv.user_id != user_id:
            return None
        conv = await self.repo.archive(thread_id, archive)
        if conv:
            await self.session.commit()
        return conv

    async def delete_conversation(self, thread_id: str, user_id: int) -> bool:
        conv = await self.repo.get_by_thread_id(thread_id)
        if not conv or conv.user_id != user_id:
            return False
        await self.repo.delete(conv)
        await self.session.commit()
        return True
