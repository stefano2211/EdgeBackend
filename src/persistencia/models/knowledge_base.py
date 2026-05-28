from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


from sqlalchemy import Index

class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        Index("idx_knowledge_base_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled_chat: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled_reactive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="knowledge_bases", lazy="selectin"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", 
        back_populates="knowledge_base", 
        lazy="selectin",
        cascade="all, delete-orphan"
    )
