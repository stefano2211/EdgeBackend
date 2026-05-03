"""MCP Source service — CRUD for MCP tool sources with auto-discovery."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.core.logging import logging
from src.persistencia.models.tool_config import MCPSource, ToolConfig
from src.persistencia.repositories.tool_repository import ToolRepository, MCPSourceRepository
from src.api.v1.schemas.tool import MCPSourceCreate, MCPSourceUpdate
from src.services._helpers import commit_and_refresh, apply_patch
from src.services.mcp_service import MCPService

logger = logging.getLogger(__name__)


class MCPSourceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MCPSourceRepository(session)
        self.tool_repo = ToolRepository(session)

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

    async def sync_source_tools(self, source_id: int) -> dict:
        """Connect to an MCP source, discover available tools, and auto-register them.

        Returns:
            {"tools_discovered": int, "tools_added": int}
        """
        source = await self.get_source(source_id)
        mcp_service = MCPService()

        discovered_tools = await mcp_service.discover_tools(
            base_url=source.url,
            is_stdio=(source.type == "stdio"),
        )

        existing_tools = await self.tool_repo.list_by_source(source_id)
        existing_names = {t.name for t in existing_tools}

        added = 0
        for tool_def in discovered_tools:
            name = tool_def.get("name")
            if not name or name in existing_names:
                continue

            tool = ToolConfig(
                name=name,
                description=tool_def.get("description") or "",
                parameter_schema=tool_def.get("parameter_schema") or tool_def.get("inputSchema") or {},
                config=tool_def.get("config", {"transport": source.type, "url": source.url}),
                source_id=source_id,
                is_enabled=True,
            )
            await self.tool_repo.create(tool)
            added += 1

        await self.session.commit()
        logger.info("Synced %d tools from MCP source %d (%d new)", len(discovered_tools), source_id, added)
        return {"tools_discovered": len(discovered_tools), "tools_added": added}
