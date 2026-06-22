"""SQLAlchemy models for the integrations subsystem.

Two entities:
  - IntegrationInstance  : per-user configured instance
  - IntegrationCredential: encrypted secret bound to an instance
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    func,
    ForeignKey,
    Integer,
    Boolean,
    JSON,
    LargeBinary,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.application.integrations.catalog_seed import CATALOG
from backend.domain.models.base import Base


class IntegrationInstance(Base):
    """A concrete integration configured by a user."""

    __tablename__ = "integration_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    catalog_slug: Mapped[str] = mapped_column(String(50), nullable=False)

    instance_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Stdio runtime (replaces Docker fields) ---
    process_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "running" | "stopped" | "error"
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Context availability ---
    available_in_chat: Mapped[bool] = mapped_column(Boolean, default=True)
    available_in_reactive: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # --- Relations ---
    credentials: Mapped[list["IntegrationCredential"]] = relationship(
        back_populates="instance", lazy="selectin", cascade="all, delete-orphan"
    )

    # ------------------------------------------------------------------
    # Read-only properties (no business logic, only data resolution)
    # ------------------------------------------------------------------

    @property
    def catalog(self):
        """Resolve the static catalog entry for this instance."""
        return CATALOG.get(self.catalog_slug)

    @property
    def catalog_id(self) -> int:
        """Stable catalog ID derived from the catalog entry."""
        if self.catalog:
            return self.catalog.id
        return 0

    @property
    def mcp_source_id(self) -> int | None:
        """Return this instance's ID if it is enabled and active."""
        if self.process_status in ("running", "ready") and self.is_enabled:
            return self.id
        return None

    @property
    def reactive_mcp_source_id(self) -> int | None:
        """Alias for mcp_source_id (reactive context)."""
        return self.mcp_source_id


class IntegrationCredential(Base):
    """Encrypted secret bound to an IntegrationInstance."""

    __tablename__ = "integration_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("integration_instances.id", ondelete="CASCADE"), nullable=False
    )

    credential_key: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # OAuth2 expiration tracking
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    encryption_key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # --- Relations ---
    instance: Mapped["IntegrationInstance"] = relationship(
        back_populates="credentials", lazy="selectin"
    )
