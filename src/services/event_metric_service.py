"""Event metric service — tracks AIOps KPIs for continuous improvement.

SOLID:
  - SRP: Only records and aggregates metrics.
  - OCP: New KPIs can be added to EventMetric without changing callers.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.event import Event
from src.persistencia.models.event_metric import EventMetric

logger = logging.getLogger(__name__)


class EventMetricService:
    """Records and updates event-related metrics (MTTD, MTTR, false-positive rate)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    async def record_event_created(self, event: Event) -> None:
        """Increment total_events counter for today's bucket."""
        metric = await self._get_or_create_bucket(
            domain=event.domain,
            event_type=event.event_type,
            date_bucket=date.today(),
        )
        metric.total_events += 1
        await self._session.flush()

    async def record_event_analyzed(self, event: Event) -> None:
        """Increment events_analyzed counter."""
        metric = await self._get_or_create_bucket(
            domain=event.domain,
            event_type=event.event_type,
            date_bucket=date.today(),
        )
        metric.events_analyzed += 1
        await self._session.flush()

    async def record_event_resolved(self, event: Event) -> None:
        """Update TTD/TTR upon resolution."""
        if not event.resolved_at or not event.created_at:
            return

        metric = await self._get_or_create_bucket(
            domain=event.domain,
            event_type=event.event_type,
            date_bucket=date.today(),
        )

        # TTD = time from event timestamp to created_at (ingestion delay)
        # TTR = time from created_at to resolved_at
        ttd_seconds = (event.created_at - event.timestamp).total_seconds()
        ttr_seconds = (event.resolved_at - event.created_at).total_seconds()

        metric.avg_ttd = self._rolling_average(metric.avg_ttd, ttd_seconds, metric.events_analyzed)
        metric.avg_ttr = self._rolling_average(metric.avg_ttr, ttr_seconds, metric.events_analyzed)

        if event.status == "completed":
            metric.events_auto_resolved += 1
        elif event.status == "failed":
            metric.events_failed += 1

        await self._session.flush()

    async def record_false_positive(self, event: Event) -> None:
        """Increment false_positive counter."""
        metric = await self._get_or_create_bucket(
            domain=event.domain,
            event_type=event.event_type,
            date_bucket=date.today(),
        )
        metric.false_positives += 1
        await self._session.flush()

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def get_metrics(
        self,
        domain: str | None = None,
        event_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[EventMetric]:
        """Fetch metrics with optional filtering."""
        stmt = select(EventMetric).order_by(EventMetric.date_bucket.desc())
        if domain:
            stmt = stmt.where(EventMetric.domain == domain)
        if event_type:
            stmt = stmt.where(EventMetric.event_type == event_type)
        if date_from:
            stmt = stmt.where(EventMetric.date_bucket >= date_from)
        if date_to:
            stmt = stmt.where(EventMetric.date_bucket <= date_to)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    def aggregate_metrics(self, metrics: list[EventMetric]) -> dict[str, Any]:
        """Aggregate a list of metric rows into a single summary dict.

        Returns keys:
            total_events, events_analyzed, events_auto_resolved, events_failed,
            false_positives, false_positive_rate, avg_ttd_seconds, avg_ttr_seconds
        """
        total_events = sum(m.total_events for m in metrics)
        events_analyzed = sum(m.events_analyzed for m in metrics)
        events_auto_resolved = sum(m.events_auto_resolved for m in metrics)
        events_failed = sum(m.events_failed for m in metrics)
        false_positives = sum(m.false_positives for m in metrics)

        avg_ttd = (
            sum(m.avg_ttd or 0 for m in metrics)
            / len([m for m in metrics if m.avg_ttd is not None])
            if any(m.avg_ttd is not None for m in metrics)
            else None
        )
        avg_ttr = (
            sum(m.avg_ttr or 0 for m in metrics)
            / len([m for m in metrics if m.avg_ttr is not None])
            if any(m.avg_ttr is not None for m in metrics)
            else None
        )

        fp_rate = false_positives / total_events if total_events > 0 else 0.0

        return {
            "total_events": total_events,
            "events_analyzed": events_analyzed,
            "events_auto_resolved": events_auto_resolved,
            "events_failed": events_failed,
            "false_positives": false_positives,
            "false_positive_rate": round(fp_rate, 4),
            "avg_ttd_seconds": round(avg_ttd, 2) if avg_ttd is not None else None,
            "avg_ttr_seconds": round(avg_ttr, 2) if avg_ttr is not None else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_or_create_bucket(
        self,
        domain: str | None,
        event_type: str | None,
        date_bucket: date,
    ) -> EventMetric:
        """Fetch existing metric row or create a new one."""
        stmt = (
            select(EventMetric)
            .where(EventMetric.domain == domain)
            .where(EventMetric.event_type == event_type)
            .where(EventMetric.date_bucket == date_bucket)
        )
        result = await self._session.execute(stmt)
        metric = result.scalar_one_or_none()

        if metric is None:
            metric = EventMetric(
                domain=domain,
                event_type=event_type,
                date_bucket=date_bucket,
            )
            self._session.add(metric)
            await self._session.flush()

        return metric

    @staticmethod
    def _rolling_average(current: float | None, new_value: float, count: int) -> float:
        """Compute new rolling average given the current average and a new value."""
        if current is None or count <= 0:
            return new_value
        if count == 1:
            # First measurement: average is just the new value
            return new_value
        return (current * (count - 1) + new_value) / count
