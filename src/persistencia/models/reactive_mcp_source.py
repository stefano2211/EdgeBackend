"""Reactive MCP Source model — isolated from chat MCP sources."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


class ReactiveMCPSource(Base):
    """MCP source exclusive to the reactive/event system, scoped per user."""

    __tablename__ = "reactive_mcp_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="rest")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(
        "User", back_populates="reactive_mcp_sources", lazy="selectin"
    )
    tools: Mapped[list["ReactiveToolConfig"]] = relationship(
        "ReactiveToolConfig", back_populates="source", lazy="selectin"
    )
