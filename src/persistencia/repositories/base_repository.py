"""Generic async CRUD repository using SQLAlchemy 2.0."""

from typing import Generic, TypeVar, Type

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: Type[T]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id: int) -> T | None:
        return await self.session.get(self.model, id)

    async def list(self, skip: int = 0, limit: int = 100) -> list[T]:
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, obj: T) -> T:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: T) -> T:
        """Merge a detached instance and return the attached version."""
        merged = await self.session.merge(obj)
        await self.session.flush()
        await self.session.refresh(merged)
        return merged

    async def delete(self, obj: T) -> None:
        await self.session.delete(obj)
        await self.session.flush()
