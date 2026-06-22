from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, LargeBinary, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.domain.models.base import Base


class DbConnectionCredential(Base):
    __tablename__ = "db_connection_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("database_connections.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    encrypted_username: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    connection: Mapped["DatabaseConnection"] = relationship(
        "DatabaseConnection", back_populates="credentials"
    )


DbCredential = DbConnectionCredential
DbConnectionCredential = DbConnectionCredential  # Keep original name too
