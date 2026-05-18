"""Domain configuration — user-defined domains for event classification.

Each user can configure multiple domains (e.g., healthcare, logistics, manufacturing)
with detection rules that the DomainDetector uses to classify incoming events.

SOLID:
  - SRP: This model only holds domain configuration data.
  - OCP: detection_rules JSON allows extending rules without schema changes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    func,
    ForeignKey,
    Integer,
    Boolean,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.persistencia.models.base import Base


class DomainConfig(Base):
    __tablename__ = "domain_configs"
    __table_args__ = (
        Index("idx_domain_config_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Detection rules stored as JSON for flexibility.
    # Example:
    # {
    #   "keywords": ["patient", "ward", "icu"],
    #   "source_patterns": ["hospital-*", "medical-device-*"],
    #   "severity_map": {"CODE_RED": "critical", "CODE_YELLOW": "warning"}
    # }
    detection_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="domain_configs")
