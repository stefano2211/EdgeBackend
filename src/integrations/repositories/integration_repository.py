"""SQLAlchemy repositories for Integration models.

Follow the Repository pattern: thin wrappers around SQLAlchemy queries.
All methods are async and accept / return domain models.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.integrations.interfaces import (
    IIntegrationCatalogRepository,
    IIntegrationInstanceRepository,
)
from src.integrations.models import IntegrationCatalog, IntegrationCredential, IntegrationInstance


class IntegrationCatalogRepository(IIntegrationCatalogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> IntegrationCatalog | None:
        result = await self._session.execute(
            select(IntegrationCatalog).where(IntegrationCatalog.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, catalog_id: int) -> IntegrationCatalog | None:
        result = await self._session.execute(
            select(IntegrationCatalog).where(IntegrationCatalog.id == catalog_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, *, enabled_only: bool = True) -> list[IntegrationCatalog]:
        stmt = select(IntegrationCatalog)
        if enabled_only:
            stmt = stmt.where(IntegrationCatalog.is_enabled.is_(True))
        stmt = stmt.order_by(IntegrationCatalog.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj: IntegrationCatalog) -> IntegrationCatalog:
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update(self, obj: IntegrationCatalog) -> IntegrationCatalog:
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete(self, obj: IntegrationCatalog) -> None:
        await self._session.delete(obj)
        await self._session.commit()


class IntegrationInstanceRepository(IIntegrationInstanceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, instance_id: int) -> IntegrationInstance | None:
        result = await self._session.execute(
            select(IntegrationInstance)
            .where(IntegrationInstance.id == instance_id)
            .options(selectinload(IntegrationInstance.catalog))
            .options(selectinload(IntegrationInstance.credentials))
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, instance_id: int, user_id: int) -> IntegrationInstance | None:
        result = await self._session.execute(
            select(IntegrationInstance)
            .where(IntegrationInstance.id == instance_id)
            .where(IntegrationInstance.user_id == user_id)
            .options(selectinload(IntegrationInstance.catalog))
            .options(selectinload(IntegrationInstance.credentials))
        )
        return result.scalar_one_or_none()

    async def create(self, obj: IntegrationInstance) -> IntegrationInstance:
        self._session.add(obj)
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def update(self, obj: IntegrationInstance) -> IntegrationInstance:
        await self._session.commit()
        await self._session.refresh(obj)
        return obj

    async def delete(self, obj: IntegrationInstance) -> None:
        await self._session.delete(obj)
        await self._session.commit()

    async def save_credentials(
        self, instance_id: int, encrypted: dict[str, bytes]
    ) -> None:
        for key, value in encrypted.items():
            cred = IntegrationCredential(
                instance_id=instance_id,
                credential_key=key,
                encrypted_value=value,
            )
            self._session.add(cred)
        await self._session.commit()

    async def list_for_user(self, user_id: int) -> list[IntegrationInstance]:
        result = await self._session.execute(
            select(IntegrationInstance)
            .where(IntegrationInstance.user_id == user_id)
            .options(selectinload(IntegrationInstance.catalog))
            .order_by(IntegrationInstance.created_at.desc())
        )
        return list(result.scalars().all())
