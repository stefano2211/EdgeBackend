"""DB Source service: CRUD for database connection configurations."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.db_source import DbSource
from src.persistencia.repositories.db_source_repository import DbSourceRepository
from src.api.v1.schemas.db_collector import DbSourceCreate, DbSourceUpdate


class DbSourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DbSourceRepository(session)

    async def list_sources(self) -> list[DbSource]:
        return await self.repo.list()

    async def get_source(self, source_id: int) -> DbSource:
        source = await self.repo.get_by_id(source_id)
        if not source:
            raise NotFoundError(f"DB Source {source_id} not found")
        return source

    async def create_source(self, data: DbSourceCreate) -> DbSource:
        source = DbSource(
            name=data.name,
            db_type=data.db_type,
            connection_string=data.connection_string,
            query=data.query,
            cron_expression=data.cron_expression,
        )
        await self.repo.create(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def update_source(self, source_id: int, data: DbSourceUpdate) -> DbSource:
        source = await self.get_source(source_id)
        if data.name is not None:
            source.name = data.name
        if data.db_type is not None:
            source.db_type = data.db_type
        if data.connection_string is not None:
            source.connection_string = data.connection_string
        if data.query is not None:
            source.query = data.query
        if data.cron_expression is not None:
            source.cron_expression = data.cron_expression
        if data.is_enabled is not None:
            source.is_enabled = data.is_enabled
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete_source(self, source_id: int) -> None:
        source = await self.get_source(source_id)
        await self.repo.delete(source)
        await self.session.commit()

    async def run_source(self, source_id: int) -> DbSource:
        """Mark a DB source as run (stub — real implementation connects and fetches)."""
        source = await self.get_source(source_id)
        source.last_run_at = datetime.now(timezone.utc)
        source.last_run_status = "success"
        await self.session.commit()
        await self.session.refresh(source)
        return source
