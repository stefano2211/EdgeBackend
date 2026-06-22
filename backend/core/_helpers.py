"""Service-layer helpers to eliminate repetitive CRUD boilerplate.

Provides:
- commit_and_refresh: one-liner for the ubiquitous session.commit + refresh pair.
- apply_patch: auto-applies Pydantic schema fields onto a SQLAlchemy instance,
  removing the endless `if data.field is not None: obj.field = data.field` blocks.
"""

from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


async def commit_and_refresh(session: AsyncSession, obj: Any) -> None:
    """Commit current transaction and refresh the object from DB."""
    await session.commit()
    await session.refresh(obj)


def apply_patch(obj: Any, data: BaseModel, *, use_set_fields: bool = True) -> None:
    """Copy non-None values from a Pydantic schema onto a SQLAlchemy model instance.

    Args:
        obj: SQLAlchemy model instance to mutate.
        data: Pydantic schema (typically an Update DTO).
        use_set_fields: If True, only copy fields that were explicitly provided
            in the request body (model_fields_set). If False, copy all defined
            fields that are not None (useful for PUT semantics).
    """
    fields = data.model_fields_set if use_set_fields else data.model_fields
    for field_name in fields:
        value = getattr(data, field_name)
        if value is not None:
            setattr(obj, field_name, value)
