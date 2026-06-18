"""Event model v3 — CloudEvents + OpenTelemetry compatible.

This model replaces the legacy Event schema with a fully generic,
sector-agnostic event representation. It supports:
  - CloudEvents core attributes (id, type, source, time, subject)
  - OpenTelemetry severity scale (1-24)
  - Arbitrary payload bodies (JSON)
  - Domain detection and correlation

Design decisions:
  - No hardcoded industrial fields. Everything generic.
  - severity_number follows OTel scale for interoperability.
  - body holds the raw payload; title/description are human-readable.
  - correlation_group_id links to EventCorrelationGroup for dedup/grouping.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    func,
    ForeignKey,
    Integer,
    JSON,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.persistencia.models.base import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_event_status", "status"),
        Index("idx_event_severity_num", "severity_number"),
        Index("idx_event_domain", "domain"),
        Index("idx_event_event_type", "event_type"),
        Index("idx_event_source", "source"),
        Index("idx_event_created_at", "created_at"),
        Index("idx_event_dedup_key", "dedup_key"),
        Index("idx_event_correlation_id", "correlation_id"),
    )

    # ── CloudEvents Core ──
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── OpenTelemetry Severity ──
    # Scale: 1-4 TRACE, 5-8 DEBUG, 9-12 INFO, 13-16 WARN, 17-20 ERROR, 21-24 FATAL
    severity_number: Mapped[int] = mapped_column(Integer, default=13, nullable=False)
    severity_text: Mapped[str] = mapped_column(String(20), default="warn", nullable=False)

    # ── Content ──
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Aura AI Extensions ──
    domain: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    subdomain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    resource: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── State Machine ──
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    suppression_reason: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # ── Agent Outputs ──
    agent_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions_taken: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Relations ──
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    correlation_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("event_correlation_groups.id", ondelete="SET NULL"), nullable=True
    )

    triggered_by: Mapped["User | None"] = relationship(
        "User", back_populates="events", lazy="selectin"
    )
    correlation_group: Mapped["EventCorrelationGroup | None"] = relationship(
        "EventCorrelationGroup", back_populates="events", lazy="selectin"
    )
