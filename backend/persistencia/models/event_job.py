"""EventJob model — tracks background analysis and execution jobs.

Provides durable, recoverable job tracking for the reactive event pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, DateTime, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.persistencia.models.base import Base


class EventJob(Base):
    __tablename__ = "event_jobs"
    __table_args__ = (
        UniqueConstraint("event_id", "job_type", name="uq_event_job_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="analysis | execution",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        comment="queued | running | completed | failed | cancelled",
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
