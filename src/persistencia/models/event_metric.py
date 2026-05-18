"""Event metrics — AIOps KPIs for observability and continuous improvement.

Tracks aggregated metrics per domain/event_type/day to enable:
  - MTTD / MTTR trending
  - False-positive rate monitoring
  - Pipeline efficiency analysis

SOLID:
  - SRP: Only aggregates and stores metrics; no calculation logic.
  - DIP: Services depend on this model, not raw SQL.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import String, Date, DateTime, func, Integer, Float, Index
from sqlalchemy.orm import Mapped, mapped_column

from src.persistencia.models.base import Base


class EventMetric(Base):
    __tablename__ = "event_metrics"
    __table_args__ = (
        Index("idx_metric_domain_date", "domain", "date_bucket"),
        Index("idx_metric_event_type_date", "event_type", "date_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    domain: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    date_bucket: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    total_events: Mapped[int] = mapped_column(Integer, default=0)
    events_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    events_auto_resolved: Mapped[int] = mapped_column(Integer, default=0)
    events_failed: Mapped[int] = mapped_column(Integer, default=0)
    false_positives: Mapped[int] = mapped_column(Integer, default=0)

    avg_ttd: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Mean Time to Detect (seconds)
    avg_ttr: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Mean Time to Resolve (seconds)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
