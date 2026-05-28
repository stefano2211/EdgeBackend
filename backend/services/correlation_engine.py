"""Event correlation engine — deduplication, flapping detection, and grouping.

Runs periodically (every 30s) to process pending events and reduce noise.

SOLID:
  - SRP: Only correlates events; no analysis or execution logic.
  - OCP: New correlation strategies can be added as methods.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.persistencia.models.event import Event
from backend.persistencia.models.event_correlation import EventCorrelationGroup

logger = logging.getLogger(__name__)

# Tunable constants
_DEDUP_WINDOW_MINUTES = 5
_FLAP_WINDOW_MINUTES = 10
_FLAP_THRESHOLD = 3
_GROUP_WINDOW_MINUTES = 15


class CorrelationEngine:
    """Processes events to deduplicate, detect flapping, and group correlated incidents."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public cycle
    # ------------------------------------------------------------------

    async def run_cycle(self) -> dict[str, int]:
        """Execute one correlation cycle. Returns counts of actions taken."""
        stats = {
            "deduplicated": 0,
            "flapping_detected": 0,
            "groups_created": 0,
            "suppressed": 0,
        }

        stats["deduplicated"] += await self._deduplicate_events()
        stats["flapping_detected"] += await self._detect_flapping()
        stats["groups_created"] += await self._group_correlated_events()
        stats["suppressed"] += await self._apply_suppression_rules()

        return stats

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    async def _deduplicate_events(self) -> int:
        """Suppress duplicate events with the same dedup_key within the window."""
        window = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=_DEDUP_WINDOW_MINUTES)

        stmt = (
            select(Event.dedup_key, func.min(Event.id))
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.dedup_key.isnot(None))
            .where(Event.created_at >= window)
            .group_by(Event.dedup_key)
            .having(func.count(Event.id) > 1)
        )
        result = await self.session.execute(stmt)
        duplicates = result.all()

        count = 0
        for dedup_key, first_id in duplicates:
            # Mark all but the first as suppressed
            suppress_stmt = (
                select(Event)
                .where(Event.dedup_key == dedup_key)
                .where(Event.id != first_id)
                .where(Event.status.in_(["pending", "analyzing"]))
            )
            to_suppress = await self.session.execute(suppress_stmt)
            for event in to_suppress.scalars().all():
                event.status = "suppressed"
                event.suppression_reason = "duplicate"
                count += 1

        if count:
            logger.info("Correlation: deduplicated %s events", count)
        return count

    # ------------------------------------------------------------------
    # Flapping detection
    # ------------------------------------------------------------------

    async def _detect_flapping(self) -> int:
        """Detect flapping: multiple events from same source in short window."""
        window = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=_FLAP_WINDOW_MINUTES)

        # Find sources with >3 events in the window (excluding already suppressed)
        stmt = (
            select(Event.source, func.count(Event.id))
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.created_at >= window)
            .where(Event.suppression_reason.is_(None))
            .group_by(Event.source)
            .having(func.count(Event.id) > _FLAP_THRESHOLD)
        )
        result = await self.session.execute(stmt)
        flapping_sources = result.all()

        count = 0
        for source, _ in flapping_sources:
            # Mark all but the earliest event from this source as flapping
            events_stmt = (
                select(Event)
                .where(Event.source == source)
                .where(Event.status.in_(["pending", "analyzing"]))
                .where(Event.created_at >= window)
                .where(Event.suppression_reason.is_(None))
                .order_by(Event.created_at.asc())
            )
            events_result = await self.session.execute(events_stmt)
            events = events_result.scalars().all()

            # Keep the first (earliest), suppress the rest
            for event in events[1:]:
                event.status = "suppressed"
                event.suppression_reason = "flapping"
                count += 1

        if count:
            logger.info("Correlation: detected %s flapping events", count)
        return count

    # ------------------------------------------------------------------
    # Grouping
    # ------------------------------------------------------------------

    async def _group_correlated_events(self) -> int:
        """Group related events by domain + source prefix + temporal proximity."""
        window = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=_GROUP_WINDOW_MINUTES)

        stmt = (
            select(Event)
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.created_at >= window)
            .where(Event.correlation_group_id.is_(None))
            .where(Event.suppression_reason.is_(None))
            .order_by(Event.created_at.asc())
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        groups_created = 0
        for event in events:
            # Look for existing active group with same domain and similar source
            group = await self._find_matching_group(event)
            if group:
                event.correlation_group_id = group.id
                group.event_count += 1
                group.last_event_at = event.created_at
                if event.severity_number > group.max_severity_number:
                    group.max_severity_number = event.severity_number
            else:
                new_group = EventCorrelationGroup(
                    correlation_id=str(uuid.uuid4())[:16],
                    group_type="temporal",
                    domain=event.domain,
                    source_pattern=event.source,
                    max_severity_number=event.severity_number,
                    event_count=1,
                    first_event_at=event.created_at,
                    last_event_at=event.created_at,
                )
                self.session.add(new_group)
                await self.session.flush()
                event.correlation_group_id = new_group.id
                groups_created += 1

        if groups_created:
            logger.info("Correlation: created %s new groups", groups_created)
        return groups_created

    async def _find_matching_group(self, event: Event) -> EventCorrelationGroup | None:
        """Find an active correlation group that matches this event."""
        window = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=_GROUP_WINDOW_MINUTES)

        stmt = (
            select(EventCorrelationGroup)
            .where(EventCorrelationGroup.status == "active")
            .where(EventCorrelationGroup.domain == event.domain)
            .where(EventCorrelationGroup.last_event_at >= window)
            .order_by(EventCorrelationGroup.last_event_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Suppression rules
    # ------------------------------------------------------------------

    async def _apply_suppression_rules(self) -> int:
        """Suppress lower-severity events when a critical is active on the same source."""
        # Find active critical events (severity >= 17 ERROR)
        critical_stmt = (
            select(Event)
            .where(Event.status.in_(["pending", "analyzing", "awaiting_approval"]))
            .where(Event.severity_number >= 17)
            .where(Event.suppression_reason.is_(None))
        )
        result = await self.session.execute(critical_stmt)
        critical_events = result.scalars().all()

        count = 0
        for critical in critical_events:
            # Suppress warnings on same source
            suppress_stmt = (
                select(Event)
                .where(Event.source == critical.source)
                .where(Event.status.in_(["pending", "analyzing"]))
                .where(Event.severity_number < 17)
                .where(Event.id != critical.id)
                .where(Event.suppression_reason.is_(None))
            )
            to_suppress = await self.session.execute(suppress_stmt)
            for event in to_suppress.scalars().all():
                event.status = "suppressed"
                event.suppression_reason = "critical_active"
                count += 1

        if count:
            logger.info("Correlation: suppressed %s events due to active critical", count)
        return count
