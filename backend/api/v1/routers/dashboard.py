"""Dashboard router — unified summary for the main landing page."""

from __future__ import annotations

import logging
import traceback
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.dashboard import DashboardSummary, RecentEventItem
from backend.core.deps import get_db, get_current_user
from backend.database_connector.models import DatabaseConnection
from backend.integrations.models import IntegrationInstance
from backend.ia.llm_client import get_llm_client
from backend.persistencia.models.event import Event
from backend.persistencia.models.user import User
from backend.persistencia.repositories.event_repository import EventRepository
from backend.services.event_metric_service import EventMetricService
from backend.services.reactive_config_service import ReactiveConfigService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    """Return a unified summary for the dashboard landing page."""
    try:
        # ── 1. Event metrics (7d) ──
        metric_service = EventMetricService(session)
        date_to = date.today()
        date_from = date_to - timedelta(days=7)
        metrics_rows = await metric_service.get_metrics(
            date_from=date_from, date_to=date_to
        )
        metrics_agg = metric_service.aggregate_metrics(metrics_rows)

        # ── 2. Events in last 24h ──
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        stmt_24h = select(func.count()).select_from(Event).where(
            Event.created_at >= cutoff_24h
        )
        res_24h = await session.execute(stmt_24h)
        total_events_24h = res_24h.scalar_one() or 0

        # ── 3. Critical pending events ──
        event_repo = EventRepository(session)
        critical_pending = await event_repo.count_with_filters(
            severity_text="critical", status="pending"
        )

        # ── 4. Events by severity (last 7d) ──
        cutoff_7d = datetime.utcnow() - timedelta(days=7)
        stmt_sev = (
            select(Event.severity_text, func.count())
            .where(Event.created_at >= cutoff_7d)
            .group_by(Event.severity_text)
        )
        res_sev = await session.execute(stmt_sev)
        events_by_severity = {sev: count for sev, count in res_sev.all()}

        # ── 5. Recent events (last 8) ──
        recent = await event_repo.list_with_filters(limit=8)
        recent_events = [
            RecentEventItem(
                id=r.id,
                event_id=r.event_id,
                title=r.title,
                severity_text=r.severity_text,
                status=r.status.value if hasattr(r.status, "value") else str(r.status),
                source=r.source,
                created_at=r.created_at,
            )
            for r in recent
        ]

        # ── 6. Active integrations (reactive-enabled) ──
        stmt_int = select(func.count()).select_from(IntegrationInstance).where(
            IntegrationInstance.user_id == current_user.id,
            IntegrationInstance.is_enabled.is_(True),
            IntegrationInstance.available_in_reactive.is_(True),
        )
        res_int = await session.execute(stmt_int)
        active_integrations = res_int.scalar_one() or 0

        # ── 7. Active knowledge bases (reactive-enabled) ──
        reactive_config = ReactiveConfigService(session)
        active_kbs = len(await reactive_config.get_enabled_knowledge_bases(current_user.id))

        # ── 8. Active DB connections (reactive-enabled) ──
        stmt_db = select(func.count()).select_from(DatabaseConnection).where(
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.available_in_reactive.is_(True),
        )
        res_db = await session.execute(stmt_db)
        active_db_connections = res_db.scalar_one() or 0

        # ── 9. System health ──
        try:
            client = get_llm_client()
            llm_status = "healthy" if client.provider else "no_llm"
        except RuntimeError:
            llm_status = "no_llm"
        system_status = "operational" if llm_status == "healthy" else "degraded"

        return DashboardSummary(
            total_events_24h=total_events_24h,
            total_events_7d=metrics_agg.get("total_events", 0),
            critical_pending=critical_pending,
            events_by_severity=events_by_severity,
            avg_ttd_seconds=metrics_agg.get("avg_ttd_seconds"),
            avg_ttr_seconds=metrics_agg.get("avg_ttr_seconds"),
            false_positive_rate=metrics_agg.get("false_positive_rate", 0.0),
            events_auto_resolved=metrics_agg.get("events_auto_resolved", 0),
            events_failed=metrics_agg.get("events_failed", 0),
            active_integrations=active_integrations,
            active_knowledge_bases=active_kbs,
            active_db_connections=active_db_connections,
            llm_status=llm_status,
            system_status=system_status,
            recent_events=recent_events,
        )
    except Exception as exc:
        logger.error("Dashboard summary error: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard backend error: {type(exc).__name__}: {exc}"
        )
