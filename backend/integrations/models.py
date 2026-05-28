"""SQLAlchemy models for the integrations subsystem.

Three entities:
  - IntegrationCatalog   : master catalogue of available integrations
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

from backend.persistencia.models.base import Base


class IntegrationCatalog(Base):
    """Master catalogue of available third-party integrations."""

    __tablename__ = "integration_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Source classification ---
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "official" | "custom" | "rest_bridge"

    # --- Runtime command (replaces Docker fields) ---
    command: Mapped[str | None] = mapped_column(String(50), nullable=True)
    args: Mapped[list | None] = mapped_column(JSON, nullable=True)
    env_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # REST bridge fallback
    rest_bridge_url_template: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Auth configuration ---
    auth_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "token" | "oauth2" | "basic" | "api_key" | "none"
    auth_env_var_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auth_setup_guide_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Flags ---
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_official_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # --- Relations ---
    instances: Mapped[list["IntegrationInstance"]] = relationship(
        back_populates="catalog", lazy="selectin"
    )


class IntegrationInstance(Base):
    """A concrete integration configured by a user."""

    __tablename__ = "integration_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    catalog_id: Mapped[int] = mapped_column(
        ForeignKey("integration_catalog.id"), nullable=False
    )

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

    # --- Linked MCP sources (auto-created on sync) ---
    mcp_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("mcp_sources.id"), nullable=True
    )
    reactive_mcp_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("reactive_mcp_sources.id"), nullable=True
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # --- Relations ---
    catalog: Mapped["IntegrationCatalog"] = relationship(
        back_populates="instances", lazy="selectin"
    )
    credentials: Mapped[list["IntegrationCredential"]] = relationship(
        back_populates="instance", lazy="selectin", cascade="all, delete-orphan"
    )


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
