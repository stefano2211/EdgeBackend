"""Junction table: which knowledge bases are enabled per user for reactive events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, Boolean, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.persistencia.models.base import Base


class UserReactiveKnowledgeBase(Base):
    """Links a user to a KnowledgeBase, tracking whether it's enabled for reactive events."""

    __tablename__ = "user_reactive_knowledge_bases"
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_base_id", name="uix_user_kb"),
        Index("idx_user_reactive_kb_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
