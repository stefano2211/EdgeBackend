from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database_connector.models import DatabaseConnection
from backend.persistencia.repositories.base_repository import BaseRepository


class DatabaseConnectionRepository(BaseRepository[DatabaseConnection]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DatabaseConnection)

    async def list_by_user(
        self, user_id: int, context: str | None = None
    ) -> list[DatabaseConnection]:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.user_id == user_id
        )
        if context == "chat":
            stmt = stmt.where(DatabaseConnection.available_in_chat == True)
        elif context == "reactive":
            stmt = stmt.where(DatabaseConnection.available_in_reactive == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id_for_user(
        self, connection_id: str, user_id: int
    ) -> DatabaseConnection | None:
        stmt = (
            select(DatabaseConnection)
            .where(DatabaseConnection.id == connection_id)
            .where(DatabaseConnection.user_id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
