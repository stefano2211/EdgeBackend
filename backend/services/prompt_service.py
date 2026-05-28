"""Prompt service: CRUD for predefined prompt templates."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.prompt import PromptCreate, PromptUpdate
from backend.persistencia.models.prompt_config import PromptConfig
from backend.persistencia.repositories.prompt_repository import PromptRepository
from backend.services.base_crud_service import BaseCRUDService


class PromptService(BaseCRUDService[PromptConfig, PromptCreate, PromptUpdate]):
    model_class = PromptConfig
    repo_class = PromptRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
