from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.models.base import Base


from sqlalchemy import Index

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_message_conversation", "conversation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    reasoning_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages", lazy="selectin"
    )
