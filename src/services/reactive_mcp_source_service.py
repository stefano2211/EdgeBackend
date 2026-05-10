"""Reactive MCP Source service — CRUD for reactive MCP tool sources with auto-discovery."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.reactive_tool import ReactiveMCPSourceCreate, ReactiveMCPSourceUpdate
from src.core.logging import logging
from src.persistencia.models.reactive_mcp_source import ReactiveMCPSource
from src.persistencia.models.reactive_tool_config import ReactiveToolConfig
from src.persistencia.repositories.reactive_tool_repository import ReactiveMCPSourceRepository, ReactiveToolRepository
from src.services.base_crud_service import BaseCRUDService
from src.services._helpers import commit_and_refresh
from src.services.mcp_service import MCPService

logger = logging.getLogger(__name__)


class ReactiveMCPSourceService(BaseCRUDService[ReactiveMCPSource, ReactiveMCPSourceCreate, ReactiveMCPSourceUpdate]):
    model_class = ReactiveMCPSource
    repo_class = ReactiveMCPSourceRepository

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.tool_repo = ReactiveToolRepository(session)

    async def sync_source_tools(self, source_id: int) -> dict:
        """Connect to a reactive MCP source, discover tools, and auto-register them.

        Returns:
            {"tools_discovered": int, "tools_added": int}
        """
        source = await self.get(source_id)
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

            tool = ReactiveToolConfig(
                name=name,
                description=tool_def.get("description") or "",
                parameter_schema=tool_def.get("parameter_schema") or tool_def.get("inputSchema") or {},
                config=tool_def.get("config", {"transport": source.type, "url": source.url}),
                source_id=source_id,
                is_enabled=True,
                user_id=source.user_id,
            )
            await self.tool_repo.create(tool)
            added += 1

        await self.session.commit()
        logger.info(
            "Synced %d tools from reactive MCP source %d (%d new)",
            len(discovered_tools), source_id, added,
        )
        return {"tools_discovered": len(discovered_tools), "tools_added": added}
