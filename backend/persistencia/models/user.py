from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.persistencia.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Notification preferences ──
    # Per-user override for reactive pipeline notifications.
    # If NULL, falls back to settings.REACTIVE_NOTIFICATION_EMAIL.
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Extensible settings JSON for future channels (slack, sms, pagerduty, etc.)
    notification_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", lazy="selectin"
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase", back_populates="user", lazy="selectin"
    )
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="triggered_by", lazy="selectin"
    )
    domain_configs: Mapped[list["DomainConfig"]] = relationship(
        "DomainConfig", back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )
