"""Event correlation — deduplication, grouping, and suppression.

The correlation engine groups related events together to reduce noise
and provide incident-level context.

SOLID:
  - SRP: CorrelationGroup tracks aggregate state of related events.
  - ISP: Minimal surface area; no logic here, only data.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.persistencia.models.base import Base


class EventCorrelationGroup(Base):
    __tablename__ = "event_correlation_groups"
    __table_args__ = (
        Index("idx_ecg_correlation_id", "correlation_id"),
        Index("idx_ecg_status", "status"),
        Index("idx_ecg_domain", "domain"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )

    group_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # dedup | resource | temporal | manual
    domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)

    max_severity_number: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | resolved | suppressed

    event_count: Mapped[int] = mapped_column(Integer, default=0)
    first_event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="correlation_group"
    )
