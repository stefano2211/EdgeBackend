"""Metrics router — AIOps KPIs and observability endpoints."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.metrics import MetricsResponse, MetricsSummary
from backend.core.deps import get_db, get_current_user
from backend.domain.models.user import User
from backend.application.events.metrics import EventMetricService

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
    agg = service.aggregate_metrics(metrics)
    return MetricsResponse(**agg)


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
    agg = service.aggregate_metrics(metrics)

    return MetricsSummary(
        total_events_last_7d=agg["total_events"],
        false_positive_rate=agg["false_positive_rate"],
    )
