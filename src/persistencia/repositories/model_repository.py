"""ModelConfig repository — BaseRepository is sufficient."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.model_config import ModelConfig
from src.persistencia.repositories.base_repository import BaseRepository


class ModelRepository(BaseRepository[ModelConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ModelConfig)
