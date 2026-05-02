"""Tool service: CRUD for ToolConfig and MCPSource."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.tool_config import ToolConfig, MCPSource
from src.persistencia.repositories.tool_repository import ToolRepository, MCPSourceRepository
from src.api.v1.schemas.tool import ToolConfigCreate, MCPSourceCreate


class ToolService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tool_repo = ToolRepository(session)
        self.source_repo = MCPSourceRepository(session)

    # ── ToolConfig ──

    async def list_tools(self) -> list[ToolConfig]:
        return await self.tool_repo.list()

    async def get_tool(self, tool_id: int) -> ToolConfig:
        tool = await self.tool_repo.get_by_id(tool_id)
        if not tool:
            raise NotFoundError(f"Tool {tool_id} not found")
        return tool

    async def create_tool(self, data: ToolConfigCreate) -> ToolConfig:
        tool = ToolConfig(
            name=data.name,
            description=data.description,
            is_enabled=data.is_enabled,
            context_mode=data.context_mode,
            config=data.config,
            parameter_schema=data.parameter_schema,
            source_id=data.source_id,
        )
        await self.tool_repo.create(tool)
        await self.session.commit()
        await self.session.refresh(tool)
        return tool

    async def update_tool(self, tool_id: int, data: ToolConfigCreate) -> ToolConfig:
        tool = await self.get_tool(tool_id)
        tool.name = data.name
        tool.description = data.description
        tool.is_enabled = data.is_enabled
        tool.context_mode = data.context_mode
        tool.config = data.config
        tool.parameter_schema = data.parameter_schema
        tool.source_id = data.source_id
        await self.session.commit()
        await self.session.refresh(tool)
        return tool

    async def delete_tool(self, tool_id: int) -> None:
        tool = await self.get_tool(tool_id)
        await self.tool_repo.delete(tool)
        await self.session.commit()

    # ── MCPSource ──

    async def list_sources(self) -> list[MCPSource]:
        return await self.source_repo.list()

    async def get_source(self, source_id: int) -> MCPSource:
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise NotFoundError(f"MCP Source {source_id} not found")
        return source

    async def create_source(self, data: MCPSourceCreate) -> MCPSource:
        source = MCPSource(
            name=data.name,
            description=data.description,
            url=data.url,
            type=data.type,
        )
        await self.source_repo.create(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def update_source(self, source_id: int, data: MCPSourceCreate) -> MCPSource:
        source = await self.get_source(source_id)
        source.name = data.name
        source.description = data.description
        source.url = data.url
        source.type = data.type
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete_source(self, source_id: int) -> None:
        source = await self.get_source(source_id)
        await self.source_repo.delete(source)
        await self.session.commit()
