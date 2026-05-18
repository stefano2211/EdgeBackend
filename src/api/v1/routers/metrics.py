"""Metrics router — AIOps KPIs and observability endpoints."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.metrics import MetricsResponse, MetricsSummary
from src.core.deps import get_db, get_current_user
from src.persistencia.models.user import User
from src.services.event_metric_service import EventMetricService

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/events", response_model=MetricsResponse)
async def get_event_metrics(
    domain: str | None = Query(None),
    event_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    """Get aggregated event metrics (MTTD, MTTR, false-positive rate, etc.)."""
    service = EventMetricService(session)
    metrics = await service.get_metrics(
        domain=domain,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
    )

    # Aggregate across returned rows
    total_events = sum(m.total_events for m in metrics)
    events_analyzed = sum(m.events_analyzed for m in metrics)
    events_auto_resolved = sum(m.events_auto_resolved for m in metrics)
    events_failed = sum(m.events_failed for m in metrics)
    false_positives = sum(m.false_positives for m in metrics)

    avg_ttd = (
        sum(m.avg_ttd or 0 for m in metrics) / len([m for m in metrics if m.avg_ttd is not None])
        if any(m.avg_ttd is not None for m in metrics)
        else None
    )
    avg_ttr = (
        sum(m.avg_ttr or 0 for m in metrics) / len([m for m in metrics if m.avg_ttr is not None])
        if any(m.avg_ttr is not None for m in metrics)
        else None
    )

    fp_rate = false_positives / total_events if total_events > 0 else 0.0

    return MetricsResponse(
        total_events=total_events,
        events_analyzed=events_analyzed,
        events_auto_resolved=events_auto_resolved,
        events_failed=events_failed,
        false_positives=false_positives,
        false_positive_rate=round(fp_rate, 4),
        avg_ttd_seconds=round(avg_ttd, 2) if avg_ttd is not None else None,
        avg_ttr_seconds=round(avg_ttr, 2) if avg_ttr is not None else None,
    )


@router.get("/events/summary", response_model=MetricsSummary)
async def get_event_metrics_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MetricsSummary:
    """Get a 7-day summary of event metrics."""
    service = EventMetricService(session)
    date_to = date.today()
    date_from = date_to - timedelta(days=7)
    metrics = await service.get_metrics(date_from=date_from, date_to=date_to)

    total_events = sum(m.total_events for m in metrics)
    fp_rate = (
        sum(m.false_positives for m in metrics) / total_events
        if total_events > 0
        else 0.0
    )

    return MetricsSummary(
        total_events_last_7d=total_events,
        false_positive_rate=round(fp_rate, 4),
    )
