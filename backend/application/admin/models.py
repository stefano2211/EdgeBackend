"""ModelConfig service — simple CRUD wrapper."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.model import ModelConfigCreate, ModelConfigUpdate
from backend.domain.models.model_config import ModelConfig
from backend.infrastructure.persistence.model_repository import ModelRepository
from backend.core.base_service import BaseCRUDService


class ModelService(BaseCRUDService[ModelConfig, ModelConfigCreate, ModelConfigUpdate]):
    model_class = ModelConfig
    repo_class = ModelRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
