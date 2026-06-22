"""Credential audit logging — tracks all credential access and mutations.

Every credential operation (access, create, update, delete, refresh) is
logged for compliance and security auditing. Credential VALUES are NEVER
logged — only metadata (key name, instance ID, action).
"""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum

from sqlalchemy import Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.models.base import Base

logger = logging.getLogger(__name__)


class CredentialAction(str, Enum):
    """Actions tracked in the credential audit log."""
    ACCESSED = "accessed"
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    REFRESHED = "refreshed"
    REFRESH_FAILED = "refresh_failed"
    DECRYPTION_FAILED = "decryption_failed"
    REENCRYPTED = "reencrypted"


class CredentialAuditLog(Base):
    """Audit trail for credential operations. Values are NEVER stored."""

    __tablename__ = "credential_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    instance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    credential_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


async def log_credential_event(
    session,
    action: CredentialAction,
    *,
    user_id: int | None = None,
    instance_id: int | None = None,
    credential_key: str | None = None,
    details: str | None = None,
) -> None:
    """Persist a credential audit event. Fire-and-forget (never raises)."""
    try:
        entry = CredentialAuditLog(
            user_id=user_id,
            instance_id=instance_id,
            action=action.value,
            credential_key=credential_key,
            details=details,
        )
        session.add(entry)
        # Don't commit here — let the caller's transaction handle it,
        # or flush to ensure the log is written even if the outer tx rolls back.
        await session.flush()
    except Exception as exc:
        # Audit logging must never break the main flow
        logger.warning("Failed to write credential audit log: %s", exc)
