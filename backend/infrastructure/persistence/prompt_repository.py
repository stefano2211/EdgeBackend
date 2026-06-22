"""PromptConfig repository — BaseRepository is sufficient."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.prompt_config import PromptConfig
from backend.infrastructure.persistence.base_repository import BaseRepository


class PromptRepository(BaseRepository[PromptConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PromptConfig)
