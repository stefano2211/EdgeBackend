"""Generic CRUD service to eliminate repetitive service boilerplate."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import NotFoundError
from backend.persistencia.models.base import Base
from backend.persistencia.repositories.base_repository import BaseRepository
from backend.services._helpers import apply_patch, commit_and_refresh

T = TypeVar("T", bound=Base)
CreateSchema = TypeVar("CreateSchema", bound=BaseModel)
UpdateSchema = TypeVar("UpdateSchema", bound=BaseModel)


class BaseCRUDService(Generic[T, CreateSchema, UpdateSchema]):
    """Reusable CRUD service layer.

    Subclasses must provide:
        - model_class: the SQLAlchemy model
        - repo_class: the repository class (must accept AsyncSession)
    """

    model_class: type[T]
    repo_class: type[BaseRepository[T]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = self.repo_class(session)

    async def list(self) -> list[T]:
        return await self.repo.list()

    async def get(self, obj_id: int) -> T:
        obj = await self.repo.get_by_id(obj_id)
        if not obj:
            raise NotFoundError(f"{self.model_class.__name__} {obj_id} not found")
        return obj

    async def create(self, data: CreateSchema) -> T:
        obj = self.model_class(**data.model_dump())
        await self.repo.create(obj)
        await commit_and_refresh(self.session, obj)
        return obj

    async def update(self, obj_id: int, data: UpdateSchema) -> T:
        obj = await self.get(obj_id)
        apply_patch(obj, data)
        await commit_and_refresh(self.session, obj)
        return obj

    async def delete(self, obj_id: int) -> None:
        obj = await self.get(obj_id)
        await self.repo.delete(obj)
        await self.session.commit()
