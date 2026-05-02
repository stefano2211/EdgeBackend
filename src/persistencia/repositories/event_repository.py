"""Event repository with filtering and status lookups."""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.event import Event
from src.persistencia.repositories.base_repository import BaseRepository


class EventRepository(BaseRepository[Event]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Event)

    async def list_with_filters(
        self,
        severity: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Event]:
        stmt = select(Event).order_by(Event.created_at.desc())
        if severity:
            stmt = stmt.where(Event.severity == severity)
        if status:
            stmt = stmt.where(Event.status == status)
        if source_type:
            stmt = stmt.where(Event.source_type == source_type)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_with_filters(
        self,
        severity: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Event)
        if severity:
            stmt = stmt.where(Event.severity == severity)
        if status:
            stmt = stmt.where(Event.status == status)
        if source_type:
            stmt = stmt.where(Event.source_type == source_type)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, id: int) -> Event | None:
        """Override to ensure Event is loaded (id is int primary key)."""
        return await self.session.get(Event, id)
