"""DB Source service: CRUD for database connection configurations."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.db_source import DbSource
from src.persistencia.repositories.db_source_repository import DbSourceRepository
from src.api.v1.schemas.db_collector import DbSourceCreate, DbSourceUpdate
from src.services._helpers import commit_and_refresh, apply_patch


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
        source = DbSource(**data.model_dump())
        await self.repo.create(source)
        await commit_and_refresh(self.session, source)
        return source

    async def update_source(self, source_id: int, data: DbSourceUpdate) -> DbSource:
        source = await self.get_source(source_id)
        apply_patch(source, data)
        await commit_and_refresh(self.session, source)
        return source

    async def delete_source(self, source_id: int) -> None:
        source = await self.get_source(source_id)
        await self.repo.delete(source)
        await self.session.commit()

    async def run_source(self, source_id: int) -> DbSource:
        """Mark a DB source as run (stub — real implementation connects and fetches)."""
        source = await self.get_source(source_id)
        source.last_run_at = datetime.now(timezone.utc).replace(tzinfo=None)
        source.last_run_status = "success"
        await commit_and_refresh(self.session, source)
        return source
