"""Reactive MCP Source service — CRUD for reactive MCP tool sources with auto-discovery."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.reactive_tool import ReactiveMCPSourceCreate, ReactiveMCPSourceUpdate
from backend.core.logging import logging
from backend.persistencia.models.reactive_mcp_source import ReactiveMCPSource
from backend.persistencia.models.reactive_tool_config import ReactiveToolConfig
from backend.persistencia.repositories.reactive_tool_repository import ReactiveMCPSourceRepository, ReactiveToolRepository
from backend.services.base_mcp_source_service import BaseMCPSourceService

logger = logging.getLogger(__name__)


class ReactiveMCPSourceService(
    BaseMCPSourceService[ReactiveMCPSource, ReactiveMCPSourceCreate, ReactiveMCPSourceUpdate, ReactiveToolConfig]
):
    model_class = ReactiveMCPSource
    repo_class = ReactiveMCPSourceRepository
    tool_model_class = ReactiveToolConfig
    tool_repo_class = ReactiveToolRepository
    _cache_context = "reactive"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
