"""ModelConfig service — simple CRUD wrapper."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.model_config import ModelConfig
from src.persistencia.repositories.model_repository import ModelRepository
from src.api.v1.schemas.model import ModelConfigCreate


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
        model = ModelConfig(
            name=data.name,
            description=data.description,
            base_model_id=data.base_model_id,
            tags=data.tags,
            system_prompt=data.system_prompt,
            params=data.params,
            knowledge_ids=data.knowledge_ids,
            tool_ids=data.tool_ids,
            skill_ids=data.skill_ids,
            capabilities=data.capabilities,
            default_features=data.default_features,
            builtin_tools=data.builtin_tools,
            tts_voice=data.tts_voice,
        )
        await self.repo.create(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def update_model(self, model_id: int, data: ModelConfigCreate) -> ModelConfig:
        """Full replacement update (PUT semantics)."""
        model = await self.get_model(model_id)
        model.name = data.name
        model.description = data.description
        model.base_model_id = data.base_model_id
        model.tags = data.tags
        model.system_prompt = data.system_prompt
        model.params = data.params
        model.knowledge_ids = data.knowledge_ids
        model.tool_ids = data.tool_ids
        model.skill_ids = data.skill_ids
        model.capabilities = data.capabilities
        model.default_features = data.default_features
        model.builtin_tools = data.builtin_tools
        model.tts_voice = data.tts_voice
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def delete_model(self, model_id: int) -> None:
        model = await self.get_model(model_id)
        await self.repo.delete(model)
        await self.session.commit()
