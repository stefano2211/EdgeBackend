"""CatalogService — CRUD for the integration catalogue.

Thin layer on top of the repository; owns business rules such as
slug uniqueness and soft-delete semantics.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.models import IntegrationCatalog
from backend.integrations.repositories import IntegrationCatalogRepository
from backend.integrations.schemas import IntegrationCatalogCreate, IntegrationCatalogUpdate

logger = logging.getLogger(__name__)


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = IntegrationCatalogRepository(session)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_slug(self, slug: str) -> IntegrationCatalog | None:
        return await self._repo.get_by_slug(slug)

    async def list_catalog(self, *, enabled_only: bool = True) -> list[IntegrationCatalog]:
        return await self._repo.list_all(enabled_only=enabled_only)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, data: IntegrationCatalogCreate) -> IntegrationCatalog:
        existing = await self._repo.get_by_slug(data.slug)
        if existing:
            raise ValueError(f"Catalog slug '{data.slug}' already exists")

        catalog = IntegrationCatalog(**data.model_dump())
        await self._repo.create(catalog)
        logger.info("Created integration catalog '%s' (%s)", data.name, data.slug)
        return catalog

    async def update(self, slug: str, data: IntegrationCatalogUpdate) -> IntegrationCatalog:
        catalog = await self._repo.get_by_slug(slug)
        if not catalog:
            raise ValueError(f"Catalog '{slug}' not found")

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(catalog, field, value)

        await self._repo.update(catalog)
        logger.info("Updated integration catalog '%s'", slug)
        return catalog

    async def delete(self, slug: str) -> None:
        catalog = await self._repo.get_by_slug(slug)
        if not catalog:
            raise ValueError(f"Catalog '{slug}' not found")
        await self._repo.delete(catalog)
        logger.info("Deleted integration catalog '%s'", slug)
