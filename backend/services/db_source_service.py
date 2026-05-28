"""DB Source service: CRUD for database connection configurations."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.db_collector import DbSourceCreate, DbSourceUpdate
from backend.persistencia.models.db_source import DbSource
from backend.persistencia.repositories.db_source_repository import DbSourceRepository
from backend.services.base_crud_service import BaseCRUDService
from backend.services._helpers import commit_and_refresh


class DbSourceService(BaseCRUDService[DbSource, DbSourceCreate, DbSourceUpdate]):
    model_class = DbSource
    repo_class = DbSourceRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def run_source(self, source_id: int) -> DbSource:
        """Mark a DB source as run (stub — real implementation connects and fetches)."""
        source = await self.get(source_id)
        source.last_run_at = datetime.now(timezone.utc).replace(tzinfo=None)
        source.last_run_status = "success"
        await commit_and_refresh(self.session, source)
        return source
