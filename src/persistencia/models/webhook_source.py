"""WebhookSource model — dynamic inbound webhook configuration.

Each webhook source defines how to map arbitrary external JSON payloads
into normalized EventIngestPayload objects via a JSON mapping_config.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    DateTime,
    Boolean,
    JSON,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.persistencia.models.base import Base


class WebhookSource(Base):
    __tablename__ = "webhook_sources"
    __table_args__ = (
        UniqueConstraint("slug", "user_id", name="uq_webhook_slug_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Dynamic mapping configuration (JSON)
    mapping_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    auto_discovered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Rate limiting
    rate_limit_rpm: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    # Statistics / debugging
    last_payload_preview: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    last_received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    total_received: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
