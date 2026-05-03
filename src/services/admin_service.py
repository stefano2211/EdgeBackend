"""Admin service: user management, system analytics, settings."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.user import User
from src.persistencia.models.conversation import Conversation
from src.persistencia.models.message import Message
from src.persistencia.models.event import Event
from src.persistencia.models.knowledge_base import KnowledgeBase
from src.persistencia.models.document import Document
from src.persistencia.repositories.user_repository import UserRepository


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    # ── Users ────────────────────────────────────────────

    async def list_users(self) -> list[User]:
        return await self.user_repo.list()

    async def get_user(self, user_id: int) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def update_user_role(self, user_id: int, role: str, is_active: bool | None = None) -> User:
        user = await self.get_user(user_id)
        user.role = role
        if is_active is not None:
            user.is_active = is_active
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_user(user_id)
        await self.user_repo.delete(user)
        await self.session.commit()

    # ── Analytics ───────────────────────────────────────

    async def get_analytics(self) -> dict:
        """Return basic system counts."""
        stmt_users = select(func.count(User.id))
        stmt_conversations = select(func.count(Conversation.id))
        stmt_messages = select(func.count(Message.id))
        stmt_events = select(func.count(Event.id))
        stmt_knowledge = select(func.count(KnowledgeBase.id))
        stmt_docs = select(func.count(Document.id))

        result_users = await self.session.execute(stmt_users)
        result_conversations = await self.session.execute(stmt_conversations)
        result_messages = await self.session.execute(stmt_messages)
        result_events = await self.session.execute(stmt_events)
        result_knowledge = await self.session.execute(stmt_knowledge)
        result_docs = await self.session.execute(stmt_docs)

        return {
            "users": result_users.scalar(),
            "conversations": result_conversations.scalar(),
            "messages": result_messages.scalar(),
            "events": result_events.scalar(),
            "knowledge_bases": result_knowledge.scalar(),
            "documents": result_docs.scalar(),
        }
