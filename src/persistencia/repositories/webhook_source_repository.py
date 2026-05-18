"""WebhookSource repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.webhook_source import WebhookSource
from src.persistencia.repositories.base_repository import BaseRepository


class WebhookSourceRepository(BaseRepository[WebhookSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WebhookSource)

    async def get_by_slug(self, slug: str) -> WebhookSource | None:
        stmt = select(WebhookSource).where(WebhookSource.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug_for_user(
        self, slug: str, user_id: int
    ) -> WebhookSource | None:
        stmt = (
            select(WebhookSource)
            .where(WebhookSource.slug == slug)
            .where(WebhookSource.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> list[WebhookSource]:
        stmt = (
            select(WebhookSource)
            .where(WebhookSource.user_id == user_id)
            .order_by(WebhookSource.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
