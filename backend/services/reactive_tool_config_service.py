"""Reactive ToolConfig service — CRUD for individual reactive tool configurations."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.reactive_tool import ReactiveToolConfigCreate, ReactiveToolConfigUpdate
from backend.persistencia.models.reactive_tool_config import ReactiveToolConfig
from backend.persistencia.repositories.reactive_tool_repository import ReactiveToolRepository
from backend.services.base_crud_service import BaseCRUDService
from backend.services._helpers import commit_and_refresh


class ReactiveToolConfigService(BaseCRUDService[ReactiveToolConfig, ReactiveToolConfigCreate, ReactiveToolConfigUpdate]):
    model_class = ReactiveToolConfig
    repo_class = ReactiveToolRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_for_user(
        self, data: ReactiveToolConfigCreate, user_id: int
    ) -> ReactiveToolConfig:
        """Create a reactive tool config scoped to a specific user."""
        obj = self.model_class(**data.model_dump(), user_id=user_id)
        await self.repo.create(obj)
        await commit_and_refresh(self.session, obj)
        return obj

    async def list_enabled_by_user(self, user_id: int) -> list[ReactiveToolConfig]:
        return await self.repo.list_enabled_by_user(user_id)
