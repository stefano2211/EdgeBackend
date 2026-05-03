"""Prompt service: CRUD for predefined prompt templates."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.prompt_config import PromptConfig
from src.persistencia.repositories.prompt_repository import PromptRepository
from src.api.v1.schemas.prompt import PromptCreate, PromptUpdate


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
        prompt = PromptConfig(
            title=data.title,
            description=data.description,
            query=data.query,
            icon=data.icon,
            system_prompt=data.system_prompt,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
        await self.repo.create(prompt)
        await self.session.commit()
        await self.session.refresh(prompt)
        return prompt

    async def update_prompt(self, prompt_id: int, data: PromptUpdate) -> PromptConfig:
        prompt = await self.get_prompt(prompt_id)
        if data.title is not None:
            prompt.title = data.title
        if data.description is not None:
            prompt.description = data.description
        if data.query is not None:
            prompt.query = data.query
        if data.icon is not None:
            prompt.icon = data.icon
        if data.system_prompt is not None:
            prompt.system_prompt = data.system_prompt
        if data.temperature is not None:
            prompt.temperature = data.temperature
        if data.max_tokens is not None:
            prompt.max_tokens = data.max_tokens
        if data.is_enabled is not None:
            prompt.is_enabled = data.is_enabled
        await self.session.commit()
        await self.session.refresh(prompt)
        return prompt

    async def delete_prompt(self, prompt_id: int) -> None:
        prompt = await self.get_prompt(prompt_id)
        await self.repo.delete(prompt)
        await self.session.commit()
