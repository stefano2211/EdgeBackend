"""DbSource repository — BaseRepository is sufficient."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.persistencia.models.db_source import DbSource
from backend.persistencia.repositories.base_repository import BaseRepository


class DbSourceRepository(BaseRepository[DbSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DbSource)
