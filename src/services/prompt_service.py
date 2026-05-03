"""Prompt service: CRUD for predefined prompt templates."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.prompt_config import PromptConfig
from src.persistencia.repositories.prompt_repository import PromptRepository
from src.api.v1.schemas.prompt import PromptCreate, PromptUpdate
from src.services._helpers import commit_and_refresh, apply_patch


class PromptService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PromptRepository(session)

    async def list_prompts(self) -> list[PromptConfig]:
        return await self.repo.list()

    async def get_prompt(self, prompt_id: int) -> PromptConfig:
        prompt = await self.repo.get_by_id(prompt_id)
        if not prompt:
            raise NotFoundError(f"Prompt {prompt_id} not found")
        return prompt

    async def create_prompt(self, data: PromptCreate) -> PromptConfig:
        prompt = PromptConfig(**data.model_dump())
        await self.repo.create(prompt)
        await commit_and_refresh(self.session, prompt)
        return prompt

    async def update_prompt(self, prompt_id: int, data: PromptUpdate) -> PromptConfig:
        prompt = await self.get_prompt(prompt_id)
        apply_patch(prompt, data)
        await commit_and_refresh(self.session, prompt)
        return prompt

    async def delete_prompt(self, prompt_id: int) -> None:
        prompt = await self.get_prompt(prompt_id)
        await self.repo.delete(prompt)
        await self.session.commit()
