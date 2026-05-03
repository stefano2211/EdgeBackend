"""MCP Source service — CRUD for MCP tool sources."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.tool_config import MCPSource
from src.persistencia.repositories.tool_repository import MCPSourceRepository
from src.api.v1.schemas.tool import MCPSourceCreate, MCPSourceUpdate
from src.services._helpers import commit_and_refresh, apply_patch


class MCPSourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MCPSourceRepository(session)

    async def list_sources(self) -> list[MCPSource]:
        return await self.repo.list()

    async def get_source(self, source_id: int) -> MCPSource:
        source = await self.repo.get_by_id(source_id)
        if not source:
            raise NotFoundError(f"MCP Source {source_id} not found")
        return source

    async def create_source(self, data: MCPSourceCreate) -> MCPSource:
        source = MCPSource(**data.model_dump())
        await self.repo.create(source)
        await commit_and_refresh(self.session, source)
        return source

    async def update_source(self, source_id: int, data: MCPSourceUpdate) -> MCPSource:
        source = await self.get_source(source_id)
        apply_patch(source, data)
        await commit_and_refresh(self.session, source)
        return source

    async def delete_source(self, source_id: int) -> None:
        source = await self.get_source(source_id)
        await self.repo.delete(source)
        await self.session.commit()
