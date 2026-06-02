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

from sqlalchemy import select, func, update
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

        # Subquery to select the first/minimum event ID for each duplicate key
        subq = (
            select(func.min(Event.id))
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.dedup_key.isnot(None))
            .where(Event.created_at >= window)
            .group_by(Event.dedup_key)
        )

        # Bulk update all other duplicate events to suppressed
        stmt = (
            update(Event)
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.dedup_key.isnot(None))
            .where(Event.created_at >= window)
            .where(Event.id.not_in(subq))
            .values(status="suppressed", suppression_reason="duplicate")
        )
        result = await self.session.execute(stmt)
        count = result.rowcount or 0

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
            select(Event.source)
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.created_at >= window)
            .where(Event.suppression_reason.is_(None))
            .group_by(Event.source)
            .having(func.count(Event.id) > _FLAP_THRESHOLD)
        )
        result = await self.session.execute(stmt)
        flapping_sources = [r[0] for r in result.all()]

        if not flapping_sources:
            return 0

        # Subquery to find the earliest event ID for each flapping source
        subq = (
            select(func.min(Event.id))
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.created_at >= window)
            .where(Event.suppression_reason.is_(None))
            .where(Event.source.in_(flapping_sources))
            .group_by(Event.source)
        )

        # Bulk update to suppress subsequent flapping events
        suppress_stmt = (
            update(Event)
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.created_at >= window)
            .where(Event.suppression_reason.is_(None))
            .where(Event.source.in_(flapping_sources))
            .where(Event.id.not_in(subq))
            .values(status="suppressed", suppression_reason="flapping")
        )
        suppress_result = await self.session.execute(suppress_stmt)
        count = suppress_result.rowcount or 0

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

        if not events:
            return 0

        # Preload active correlation groups to avoid N+1 queries in the loop
        active_groups_stmt = (
            select(EventCorrelationGroup)
            .where(EventCorrelationGroup.status == "active")
            .where(EventCorrelationGroup.last_event_at >= window)
            .order_by(EventCorrelationGroup.last_event_at.desc())
        )
        groups_result = await self.session.execute(active_groups_stmt)
        active_groups = list(groups_result.scalars().all())

        groups_created = 0
        for event in events:
            # Find matching group in preloaded memory list
            group = None
            for g in active_groups:
                if g.domain == event.domain:
                    group = g
                    break

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
                active_groups.insert(0, new_group)  # Pre-fill for subsequent matches in the loop
                groups_created += 1

        if groups_created:
            logger.info("Correlation: created %s new groups", groups_created)
        return groups_created

    # ------------------------------------------------------------------
    # Suppression rules
    # ------------------------------------------------------------------

    async def _apply_suppression_rules(self) -> int:
        """Suppress lower-severity events when a critical is active on the same source."""
        # Find sources of active critical events (severity >= 17 ERROR)
        critical_stmt = (
            select(Event.source)
            .where(Event.status.in_(["pending", "analyzing", "awaiting_approval"]))
            .where(Event.severity_number >= 17)
            .where(Event.suppression_reason.is_(None))
        )
        result = await self.session.execute(critical_stmt)
        critical_sources = [r[0] for r in result.all()]

        if not critical_sources:
            return 0

        # Subquery to ensure we do not suppress critical events themselves
        critical_ids_stmt = (
            select(Event.id)
            .where(Event.status.in_(["pending", "analyzing", "awaiting_approval"]))
            .where(Event.severity_number >= 17)
            .where(Event.suppression_reason.is_(None))
        )

        # Bulk update to suppress warnings on those critical sources
        suppress_stmt = (
            update(Event)
            .where(Event.source.in_(critical_sources))
            .where(Event.status.in_(["pending", "analyzing"]))
            .where(Event.severity_number < 17)
            .where(Event.id.not_in(critical_ids_stmt))
            .where(Event.suppression_reason.is_(None))
            .values(status="suppressed", suppression_reason="critical_active")
        )
        suppress_result = await self.session.execute(suppress_stmt)
        count = suppress_result.rowcount or 0

        if count:
            logger.info("Correlation: suppressed %s events due to active critical", count)
        return count
