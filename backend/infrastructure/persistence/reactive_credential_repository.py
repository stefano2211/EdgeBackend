"""Repository for ReactiveCredential model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.reactive_credential import ReactiveCredential
from backend.infrastructure.persistence.base_repository import BaseRepository


class ReactiveCredentialRepository(BaseRepository[ReactiveCredential]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReactiveCredential)

    async def list_by_user(self, user_id: int) -> list[ReactiveCredential]:
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_key(self, key_identifier: str) -> ReactiveCredential | None:
        stmt = select(self.model).where(self.model.key_identifier == key_identifier)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, cred_id: int, user_id: int) -> ReactiveCredential | None:
        stmt = select(self.model).where(
            self.model.id == cred_id,
            self.model.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
