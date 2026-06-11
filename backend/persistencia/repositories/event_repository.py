"""Event repository with filtering and status lookups.

Follows Repository pattern: thin async wrapper around SQLAlchemy queries.
"""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.persistencia.models.event import Event
from backend.persistencia.repositories.base_repository import BaseRepository


class EventRepository(BaseRepository[Event]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Event)

    async def list_with_filters(
        self,
        severity_text: str | None = None,
        status: str | None = None,
        domain: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Event]:
        stmt = select(Event).order_by(Event.created_at.desc())
        if severity_text:
            stmt = stmt.where(Event.severity_text == severity_text)
        if status:
            stmt = stmt.where(Event.status == status)
        if domain:
            stmt = stmt.where(Event.domain == domain)
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        if source:
            stmt = stmt.where(Event.source == source)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_with_filters(
        self,
        severity_text: str | None = None,
        status: str | None = None,
        domain: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Event)
        if severity_text:
            stmt = stmt.where(Event.severity_text == severity_text)
        if status:
            stmt = stmt.where(Event.status == status)
        if domain:
            stmt = stmt.where(Event.domain == domain)
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)
        if source:
            stmt = stmt.where(Event.source == source)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, id: int) -> Event | None:
        """Fetch event by integer primary key."""
        return await self.session.get(Event, id)

    async def get_by_event_id(self, event_id: str) -> Event | None:
        """Fetch event by CloudEvents event_id (UUID string)."""
        stmt = select(Event).where(Event.event_id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_for_correlation(self, limit: int = 100) -> list[Event]:
        """Fetch events eligible for correlation processing."""
        stmt = (
            select(Event)
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.suppression_reason.is_(None))
            .order_by(Event.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_by_dedup_key(
        self, dedup_key: str, minutes: int = 5
    ) -> Event | None:
        """Check for a recent non-suppressed event with the same dedup key."""
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes)
        stmt = (
            select(Event)
            .where(Event.dedup_key == dedup_key)
            .where(Event.created_at >= cutoff)
            .where(Event.status != "suppressed")
            .order_by(Event.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
