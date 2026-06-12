from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, Integer, Boolean, Text, ForeignKey, UniqueConstraint, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from backend.persistencia.models.base import Base


class DbSource(Base):
    __tablename__ = "db_sources"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_db_source_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    db_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Encrypted connection string (CredentialVault)
    connection_string: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    cron_expression: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
