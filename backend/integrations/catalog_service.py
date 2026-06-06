"""CatalogService — lookup for the static integration catalogue."""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.catalog import CATALOG, IntegrationCatalogConfig

logger = logging.getLogger(__name__)


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        # DB session is kept for API dependency compatibility but not used
        self._session = session

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_by_slug(self, slug: str) -> IntegrationCatalogConfig | None:
        return CATALOG.get(slug)

    async def list_catalog(self, *, enabled_only: bool = True) -> list[IntegrationCatalogConfig]:
        return [c for c in CATALOG.values() if not enabled_only or c.is_enabled]
