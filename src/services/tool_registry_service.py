"""Tool registry service — unified view of all MCP tools across chat and reactive contexts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.integrations.models import IntegrationCatalog, IntegrationInstance
from src.persistencia.models.reactive_mcp_source import ReactiveMCPSource
from src.persistencia.models.reactive_tool_config import ReactiveToolConfig
from src.persistencia.models.tool_config import MCPSource, ToolConfig


class ToolRegistryService:
    """Build a unified registry of active MCP tools with integration metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_registry(self) -> list[dict]:
        """Return all active MCP tools across chat and reactive contexts."""
        registry: list[dict] = []

        # ── Chat tools ──
        chat_stmt = (
            select(ToolConfig, MCPSource)
            .join(MCPSource, ToolConfig.source_id == MCPSource.id)
            .where(ToolConfig.is_enabled.is_(True))
            .options(
                selectinload(MCPSource.tools),
            )
        )
        chat_result = await self.session.execute(chat_stmt)

        for tool, source in chat_result.unique().all():
            meta = await self._resolve_integration_meta(source.id, "mcp_source_id")
            registry.append(
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    "source_name": source.name,
                    "source_type": meta.get("source_type", "stdio"),
                    "context": getattr(source, "context_mode", "chat"),
                    "transport": tool.config.get("transport", source.type)
                    if tool.config
                    else source.type,
                    "is_enabled": tool.is_enabled,
                    "category": meta.get("category"),
                    "instance_name": meta.get("instance_name"),
                    "created_at": tool.created_at,
                }
            )

        # ── Reactive tools ──
        reactive_stmt = (
            select(ReactiveToolConfig, ReactiveMCPSource)
            .join(
                ReactiveMCPSource,
                ReactiveToolConfig.source_id == ReactiveMCPSource.id,
            )
            .where(ReactiveToolConfig.is_enabled.is_(True))
            .options(
                selectinload(ReactiveMCPSource.tools),
            )
        )
        reactive_result = await self.session.execute(reactive_stmt)

        for tool, source in reactive_result.unique().all():
            meta = await self._resolve_integration_meta(
                source.id, "reactive_mcp_source_id"
            )
            registry.append(
                {
                    "id": tool.id,
                    "name": tool.name,
                    "description": tool.description,
                    "source_name": source.name,
                    "source_type": meta.get("source_type", "stdio"),
                    "context": "reactive",
                    "transport": tool.config.get("transport", source.type)
                    if tool.config
                    else source.type,
                    "is_enabled": tool.is_enabled,
                    "category": meta.get("category"),
                    "instance_name": meta.get("instance_name"),
                    "created_at": tool.created_at,
                }
            )

        return registry

    async def _resolve_integration_meta(
        self, source_id: int, source_field: str
    ) -> dict:
        """Fetch integration catalog metadata for a given MCP source."""
        stmt = (
            select(IntegrationInstance, IntegrationCatalog)
            .join(
                IntegrationCatalog,
                IntegrationInstance.catalog_id == IntegrationCatalog.id,
            )
            .where(getattr(IntegrationInstance, source_field) == source_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row:
            instance, catalog = row
            return {
                "source_type": catalog.source_type,
                "instance_name": instance.instance_name,
                "category": getattr(catalog, "category", None),
            }
        return {}
