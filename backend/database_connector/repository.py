from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database_connector.models import DatabaseConnection
from backend.persistencia.repositories.base_repository import BaseRepository

class DatabaseConnectionRepository(BaseRepository[DatabaseConnection]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DatabaseConnection)

    async def list_by_user(self, user_id: int) -> list[DatabaseConnection]:
        stmt = select(self.model).where(self.model.user_id == user_id).order_by(self.model.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_active_by_user(self, user_id: int, context: str) -> list[DatabaseConnection]:
        stmt = select(self.model).where(
            self.model.user_id == user_id,
            self.model.status == "connected"
        )
        if context == "chat":
            stmt = stmt.where(self.model.available_in_chat == True)
        elif context == "reactive":
            stmt = stmt.where(self.model.available_in_reactive == True)
        stmt = stmt.order_by(self.model.created_at.desc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
