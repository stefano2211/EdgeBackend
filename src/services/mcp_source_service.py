"""MCP Source service — CRUD for MCP tool sources with auto-discovery."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.tool import MCPSourceCreate, MCPSourceUpdate
from src.core.logging import logging
from src.persistencia.models.tool_config import MCPSource, ToolConfig
from src.persistencia.repositories.tool_repository import MCPSourceRepository, ToolRepository
from src.services.base_mcp_source_service import BaseMCPSourceService

logger = logging.getLogger(__name__)


class MCPSourceService(
    BaseMCPSourceService[MCPSource, MCPSourceCreate, MCPSourceUpdate, ToolConfig]
):
    model_class = MCPSource
    repo_class = MCPSourceRepository
    tool_model_class = ToolConfig
    tool_repo_class = ToolRepository
    _cache_context = "chat"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
