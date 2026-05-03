"""Admin service: user management, system analytics, settings."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.user import User
from src.persistencia.repositories.user_repository import UserRepository
from src.services._helpers import commit_and_refresh


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
        await commit_and_refresh(self.session, user)
        return user

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_user(user_id)
        await self.user_repo.delete(user)
        await self.session.commit()

    # ── Analytics ───────────────────────────────────────

    async def get_analytics(self) -> dict:
        """Return basic system counts via repository aggregation."""
        return {
            "users": await self.user_repo.count(),
            "conversations": 0,   # TODO: add ConversationRepository.count()
            "messages": 0,          # TODO: add MessageRepository.count()
            "events": 0,          # TODO: add EventRepository.count()
            "knowledge_bases": 0,   # TODO: add KnowledgeRepository.count()
            "documents": 0,       # TODO: add DocumentRepository.count()
        }
