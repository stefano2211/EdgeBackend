"""User feedback — human-in-the-loop signal for model improvement.

Users can mark events as false positives or incorrect diagnoses.
This feedback feeds into metric tracking and future model tuning.

SOLID:
  - SRP: Only stores feedback records.
  - ISP: Minimal fields, extensible via feedback_type enum.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.persistencia.models.base import Base


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    feedback_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # false_positive | incorrect_diagnosis | wrong_severity | other
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
