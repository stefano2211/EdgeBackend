from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


from sqlalchemy import Index

class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_event_status", "status"),
        Index("idx_event_severity", "severity"),
        Index("idx_event_source_type", "source_type"),
        Index("idx_event_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(36), default="default")
    source_type: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    actions_taken: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triggered_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    triggered_by: Mapped["User | None"] = relationship(
        "User", back_populates="events", lazy="selectin"
    )
