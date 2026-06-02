from __future__ import annotations

from datetime import datetime
from enum import Enum
import uuid

from sqlalchemy import String, DateTime, func, Integer, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.persistencia.models.base import Base


class DbType(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_readonly: Mapped[bool] = mapped_column(Boolean, default=True)
    max_rows: Mapped[int] = mapped_column(Integer, default=1000)
    query_timeout: Mapped[int] = mapped_column(Integer, default=30)
    available_in_chat: Mapped[bool] = mapped_column(Boolean, default=True)
    available_in_reactive: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # enriched metadata: fk_graph, stats, descriptions
    last_schema_sync: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=ConnectionStatus.DISCONNECTED
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", lazy="selectin")
    credentials: Mapped["DbConnectionCredential | None"] = relationship(
        "DbConnectionCredential",
        back_populates="connection",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
