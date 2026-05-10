"""Reactive Tool Config model — isolated from chat tools."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


class ReactiveToolConfig(Base):
    """Tool configuration exclusive to the reactive/event system, scoped per user."""

    __tablename__ = "reactive_tool_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parameter_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("reactive_mcp_sources.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="reactive_tool_configs", lazy="selectin"
    )
    source: Mapped["ReactiveMCPSource | None"] = relationship(
        "ReactiveMCPSource", back_populates="tools", lazy="selectin"
    )
