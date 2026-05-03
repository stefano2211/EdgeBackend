"""ToolConfig service — CRUD for individual tool configurations."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.tool_config import ToolConfig
from src.persistencia.repositories.tool_repository import ToolRepository
from src.api.v1.schemas.tool import ToolConfigCreate, ToolConfigUpdate
from src.services._helpers import commit_and_refresh, apply_patch


class ToolConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ToolRepository(session)

    async def list_tools(self) -> list[ToolConfig]:
        return await self.repo.list()

    async def get_tool(self, tool_id: int) -> ToolConfig:
        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise NotFoundError(f"Tool {tool_id} not found")
        return tool

    async def create_tool(self, data: ToolConfigCreate) -> ToolConfig:
        tool = ToolConfig(**data.model_dump())
        await self.repo.create(tool)
        await commit_and_refresh(self.session, tool)
        return tool

    async def update_tool(self, tool_id: int, data: ToolConfigUpdate) -> ToolConfig:
        tool = await self.get_tool(tool_id)
        apply_patch(tool, data)
        await commit_and_refresh(self.session, tool)
        return tool

    async def delete_tool(self, tool_id: int) -> None:
        tool = await self.get_tool(tool_id)
        await self.repo.delete(tool)
        await self.session.commit()
