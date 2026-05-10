"""Reactive Document model — isolated from chat documents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


class ReactiveDocument(Base):
    """Document uploaded into a reactive knowledge base."""

    __tablename__ = "reactive_documents"
    __table_args__ = (
        Index("idx_reactive_doc_kb", "reactive_knowledge_base_id"),
        Index("idx_reactive_doc_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reactive_knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("reactive_knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    # Full S3 key: reactive_kb/{reactive_knowledge_base_id}/{uuid}.{ext}
    file_id: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    qdrant_collection: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reactive_knowledge_base: Mapped["ReactiveKnowledgeBase"] = relationship(
        "ReactiveKnowledgeBase", back_populates="documents", lazy="selectin"
    )
