"""SQLAlchemy repositories for Integration models.

Follow the Repository pattern: thin wrappers around SQLAlchemy queries.
All methods are async and accept / return domain models.
"""

from __future__ import annotations

from datetime import timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.domain.ports.integration_ports import (
    IIntegrationInstanceRepository,
)
from backend.domain.models.integration_instance import IntegrationCredential, IntegrationInstance


class IntegrationInstanceRepository(IIntegrationInstanceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def get_by_id(self, instance_id: int) -> IntegrationInstance | None:
        result = await self._session.execute(
            select(IntegrationInstance)
            .where(IntegrationInstance.id == instance_id)
            .options(selectinload(IntegrationInstance.credentials))
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, instance_id: int, user_id: int) -> IntegrationInstance | None:
        result = await self._session.execute(
            select(IntegrationInstance)
            .where(IntegrationInstance.id == instance_id)
            .where(IntegrationInstance.user_id == user_id)
            .options(selectinload(IntegrationInstance.credentials))
        )
        return result.scalar_one_or_none()

    async def create(self, obj: IntegrationInstance) -> IntegrationInstance:
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update(self, obj: IntegrationInstance) -> IntegrationInstance:
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete(self, obj: IntegrationInstance) -> None:
        await self._session.delete(obj)
        await self._session.commit()

    async def delete_credentials(self, instance_id: int) -> None:
        stmt = (
            select(IntegrationCredential)
            .where(IntegrationCredential.instance_id == instance_id)
        )
        result = await self._session.execute(stmt)
        for cred in result.scalars().all():
            await self._session.delete(cred)
        await self._session.commit()

    async def save_credentials(
        self, instance_id: int, encrypted: dict[str, bytes], expires_at_map: dict[str, Any] | None = None
    ) -> None:
        # Prevent duplicate credentials by removing any existing ones first
        await self.delete_credentials(instance_id)
        for key, value in encrypted.items():
            expires_at = expires_at_map.get(key) if expires_at_map else None
            if expires_at is not None and expires_at.tzinfo is not None:
                expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
            cred = IntegrationCredential(
                instance_id=instance_id,
                credential_key=key,
                encrypted_value=value,
                expires_at=expires_at,
            )
            self._session.add(cred)
        await self._session.commit()

    async def list_for_user(self, user_id: int) -> list[IntegrationInstance]:
        result = await self._session.execute(
            select(IntegrationInstance)
            .where(IntegrationInstance.user_id == user_id)
            .order_by(IntegrationInstance.created_at.desc())
        )
        return list(result.scalars().all())
