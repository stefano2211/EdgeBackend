from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, Integer, Boolean, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.persistencia.models.base import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    knowledge_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    tool_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
