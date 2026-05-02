from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Boolean, JSON, Text
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
    context_mode: Mapped[str] = mapped_column(String(20), default="both")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tools: Mapped[list["ToolConfig"]] = relationship(
        "ToolConfig", back_populates="source", lazy="selectin"
    )


class ToolConfig(Base):
    __tablename__ = "tool_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    context_mode: Mapped[str] = mapped_column(String(20), default="both")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parameter_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("mcp_sources.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source: Mapped["MCPSource | None"] = relationship(
        "MCPSource", back_populates="tools", lazy="selectin"
    )
