"""ModelConfig service — simple CRUD wrapper."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.model import ModelConfigCreate, ModelConfigUpdate
from backend.persistencia.models.model_config import ModelConfig
from backend.persistencia.repositories.model_repository import ModelRepository
from backend.services.base_crud_service import BaseCRUDService


class ModelService(BaseCRUDService[ModelConfig, ModelConfigCreate, ModelConfigUpdate]):
    model_class = ModelConfig
    repo_class = ModelRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
