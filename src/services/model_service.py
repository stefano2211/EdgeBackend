"""ModelConfig service — simple CRUD wrapper."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.model_config import ModelConfig
from src.persistencia.repositories.model_repository import ModelRepository
from src.api.v1.schemas.model import ModelConfigCreate, ModelConfigUpdate
from src.services._helpers import commit_and_refresh, apply_patch


class ModelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ModelRepository(session)

    async def list_models(self) -> list[ModelConfig]:
        return await self.repo.list()

    async def get_model(self, model_id: int) -> ModelConfig:
        model = await self.repo.get_by_id(model_id)
        if not model:
            raise NotFoundError(f"Model {model_id} not found")
        return model

    async def create_model(self, data: ModelConfigCreate) -> ModelConfig:
        model = ModelConfig(**data.model_dump())
        await self.repo.create(model)
        await commit_and_refresh(self.session, model)
        return model

    async def update_model(self, model_id: int, data: ModelConfigUpdate) -> ModelConfig:
        """Partial update (PATCH semantics)."""
        model = await self.get_model(model_id)
        apply_patch(model, data)
        await commit_and_refresh(self.session, model)
        return model

    async def delete_model(self, model_id: int) -> None:
        model = await self.get_model(model_id)
        await self.repo.delete(model)
        await self.session.commit()
