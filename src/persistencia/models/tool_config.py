from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Boolean, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


class MCPSource(Base):
    __tablename__ = "mcp_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="rest")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    context_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tools: Mapped[list["ToolConfig"]] = relationship(
        "ToolConfig",
        back_populates="source",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ToolConfig(Base):
    __tablename__ = "tool_configs"
    __table_args__ = (
        UniqueConstraint("source_id", "name", name="uq_tool_config_source_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parameter_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("mcp_sources.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    source: Mapped["MCPSource | None"] = relationship(
        "MCPSource", back_populates="tools", lazy="selectin"
    )
