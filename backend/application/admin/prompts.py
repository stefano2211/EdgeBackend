"""Prompt service: CRUD for predefined prompt templates."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.prompt import PromptCreate, PromptUpdate
from backend.domain.models.prompt_config import PromptConfig
from backend.infrastructure.persistence.prompt_repository import PromptRepository
from backend.core.base_service import BaseCRUDService


class PromptService(BaseCRUDService[PromptConfig, PromptCreate, PromptUpdate]):
    model_class = PromptConfig
    repo_class = PromptRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
