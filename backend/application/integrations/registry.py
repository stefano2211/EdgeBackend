"""Tool registry service — unified dynamic view of all active MCP tools."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.integration_instance import IntegrationInstance
from backend.application.integrations.service import IntegrationService
from backend.presentation.schemas.tool import MCPRegistryItem


class ToolRegistryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_registry(self, user_id: int) -> list[MCPRegistryItem]:
        """List active MCP tools dynamically across contexts for a given user."""
        stmt = select(IntegrationInstance).where(
            IntegrationInstance.user_id == user_id,
            IntegrationInstance.is_enabled.is_(True)
        )
        result = await self.session.execute(stmt)
        instances = result.scalars().all()

        integration_service = IntegrationService(self.session)
        registry_items = []

        for instance in instances:
            discovered = await integration_service._discover_tools(instance)
            catalog = instance.catalog
            if not catalog:
                continue

            # Determine contexts
            if instance.available_in_chat and instance.available_in_reactive:
                context = "both"
            elif instance.available_in_chat:
                context = "chat"
            elif instance.available_in_reactive:
                context = "reactive"
            else:
                continue

            for t in discovered:
                tool_name = t["name"]
                tool_id = abs(hash(f"{instance.id}:{tool_name}")) % 1000000 + 1
                config = t.get("config") or {}
                transport = config.get("transport", "stdio")

                registry_items.append(
                    MCPRegistryItem(
                        id=tool_id,
                        name=tool_name,
                        description=t.get("description") or "",
                        source_name=f"{catalog.slug}-u{instance.user_id}-i{instance.id}",
                        source_type=catalog.source_type,
                        context=context,
                        transport=transport,
                        is_enabled=True,
                        category=catalog.category,
                        instance_name=instance.instance_name,
                        created_at=instance.created_at,
                    )
                )

        return registry_items
