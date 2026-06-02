from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Boolean, JSON, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.persistencia.models.base import Base

class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)  # postgresql, mysql, sqlite, mssql
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    schema_name: Mapped[str | None] = mapped_column(String(255), default="public", nullable=True)
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_rows: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    query_timeout: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    available_in_chat: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    available_in_reactive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovered_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_schema_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="disconnected", nullable=False)  # connected, error, disconnected
    status_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", lazy="selectin")
