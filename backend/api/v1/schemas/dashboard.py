"""Dashboard summary schema."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RecentEventItem(BaseModel):
    id: int
    event_id: str
    title: str
    severity_text: str
    status: str
    source: str
    created_at: datetime


class DashboardSummary(BaseModel):
    # Event counts
    total_events_24h: int
    total_events_7d: int
    critical_pending: int
    events_by_severity: dict[str, int]

    # AIOps metrics
    avg_ttd_seconds: Optional[float]
    avg_ttr_seconds: Optional[float]
    false_positive_rate: float
    events_auto_resolved: int
    events_failed: int

    # Resources
    active_integrations: int
    active_knowledge_bases: int
    active_db_connections: int

    # System health
    llm_status: str
    system_status: str

    # Recent activity
    recent_events: list[RecentEventItem]
