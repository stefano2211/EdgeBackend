"""Junction table: which tools are enabled per user for reactive events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, Boolean, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.persistencia.models.base import Base


class UserReactiveTool(Base):
    """Links a user to a ToolConfig, tracking whether it's enabled for reactive events."""

    __tablename__ = "user_reactive_tools"
    __table_args__ = (
        UniqueConstraint("user_id", "tool_config_id", name="uix_user_tool"),
        Index("idx_user_reactive_tools_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_config_id: Mapped[int] = mapped_column(
        ForeignKey("tool_configs.id", ondelete="CASCADE"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
