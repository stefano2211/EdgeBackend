from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.models.base import Base


from sqlalchemy import Index

class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_document_kb", "knowledge_base_id"),
        Index("idx_document_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    # Full S3 key: kb/{knowledge_base_id}/{uuid}.{ext} (up to ~500 chars)
    file_id: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    qdrant_collection: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", back_populates="documents", lazy="selectin"
    )
