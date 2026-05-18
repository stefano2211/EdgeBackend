"""DomainConfig repository — thin CRUD wrapper.

Follows the Repository pattern for testability and separation of concerns.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.domain_config import DomainConfig
from src.persistencia.repositories.base_repository import BaseRepository


class DomainConfigRepository(BaseRepository[DomainConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DomainConfig)

    async def list_for_user(self, user_id: int) -> list[DomainConfig]:
        stmt = (
            select(DomainConfig)
            .where(DomainConfig.user_id == user_id)
            .where(DomainConfig.is_enabled.is_(True))
            .order_by(DomainConfig.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_default_for_user(self, user_id: int) -> DomainConfig | None:
        stmt = (
            select(DomainConfig)
            .where(DomainConfig.user_id == user_id)
            .where(DomainConfig.is_default.is_(True))
            .where(DomainConfig.is_enabled.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name_for_user(self, user_id: int, name: str) -> DomainConfig | None:
        stmt = (
            select(DomainConfig)
            .where(DomainConfig.user_id == user_id)
            .where(DomainConfig.name == name)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
