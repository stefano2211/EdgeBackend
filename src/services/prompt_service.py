"""Prompt service: CRUD for predefined prompt templates."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.prompt import PromptCreate, PromptUpdate
from src.persistencia.models.prompt_config import PromptConfig
from src.persistencia.repositories.prompt_repository import PromptRepository
from src.services.base_crud_service import BaseCRUDService


class PromptService(BaseCRUDService[PromptConfig, PromptCreate, PromptUpdate]):
    model_class = PromptConfig
    repo_class = PromptRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
