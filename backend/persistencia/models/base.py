"""Base SQLAlchemy declarative class and mixins."""

from datetime import datetime, timezone
from typing import Annotated

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── Type shortcuts ──
int_pk = Annotated[int, mapped_column(primary_key=True, autoincrement=True)]
created_at = Annotated[
    datetime,
    mapped_column(insert_default=func.now(), nullable=False),
]
updated_at = Annotated[
    datetime,
    mapped_column(insert_default=func.now(), onupdate=func.now(), nullable=False),
]
