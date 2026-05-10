"""Reactive Knowledge Base model — isolated from chat knowledge bases."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


class ReactiveKnowledgeBase(Base):
    """Knowledge base exclusive to the reactive/event system."""

    __tablename__ = "reactive_knowledge_bases"
    __table_args__ = (
        Index("idx_reactive_kb_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="reactive_knowledge_bases", lazy="selectin"
    )
    documents: Mapped[list["ReactiveDocument"]] = relationship(
        "ReactiveDocument",
        back_populates="reactive_knowledge_base",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
