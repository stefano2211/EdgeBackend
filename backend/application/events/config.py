"""Business logic for reactive user configuration.

Reads directly from unified KnowledgeBase table using is_enabled_reactive field,
plus IntegrationInstance for active tools dynamically.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.persistence.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class ReactiveConfigService:
    """Facade for reactive configuration management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._kb_repo = KnowledgeRepository(session)

    async def list_tools(self, user_id: int) -> list[dict]:
        """Return all reactive tools for the user dynamically."""
        from sqlalchemy import select
        from backend.domain.models.integration_instance import IntegrationInstance
        from backend.application.integrations.service import IntegrationService

        stmt = select(IntegrationInstance).where(
            IntegrationInstance.user_id == user_id,
            IntegrationInstance.is_enabled.is_(True),
            IntegrationInstance.available_in_reactive.is_(True),
        )
        result = await self._session.execute(stmt)
        instances = result.scalars().all()

        integration_service = IntegrationService(self._session)
        tools_out = []
        for instance in instances:
            discovered = await integration_service._discover_tools(instance)
            for t in discovered:
                tool_name = t["name"]
                tool_id = abs(hash(f"{instance.id}:{tool_name}")) % 1000000 + 1
                tools_out.append({
                    "id": tool_id,
                    "name": tool_name,
                    "description": t.get("description") or "",
                    "is_enabled": instance.available_in_reactive,
                    "user_id": user_id,
                    "source_name": instance.instance_name,
                })
        return tools_out

    async def toggle_tool(self, user_id: int, tool_id: int, enabled: bool) -> None:
        """Enable or disable a reactive tool by toggling its parent integration's reactive status."""
        from sqlalchemy import select
        from backend.domain.models.integration_instance import IntegrationInstance
        from backend.application.integrations.service import IntegrationService

        stmt = select(IntegrationInstance).where(
            IntegrationInstance.user_id == user_id,
            IntegrationInstance.is_enabled.is_(True),
        )
        result = await self._session.execute(stmt)
        instances = result.scalars().all()

        integration_service = IntegrationService(self._session)
        for instance in instances:
            discovered = await integration_service._discover_tools(instance)
            for t in discovered:
                tool_name = t["name"]
                current_tool_id = abs(hash(f"{instance.id}:{tool_name}")) % 1000000 + 1
                if current_tool_id == tool_id:
                    instance.available_in_reactive = enabled
                    await self._session.commit()
                    logger.info(
                        "User %s %s reactive availability for integration %s (tool %s)",
                        user_id,
                        "enabled" if enabled else "disabled",
                        instance.instance_name,
                        tool_name,
                    )
                    return

    async def list_knowledge_bases(self, user_id: int) -> list[dict]:
        """Return all reactive-enabled KBs for the user."""
        kbs = await self._kb_repo.list_enabled_for_reactive(user_id)
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "is_enabled": kb.is_enabled_reactive,
                "document_count": len(kb.documents),
            }
            for kb in kbs
        ]

    async def toggle_knowledge_base(self, user_id: int, kb_id: int, enabled: bool) -> None:
        """Enable or disable a reactive knowledge base."""
        kb = await self._kb_repo.get_by_id_for_user(kb_id, user_id)
        if kb:
            kb.is_enabled_reactive = enabled
            await self._session.commit()
            logger.info(
                "User %s %s reactive KB %s",
                user_id,
                "enabled" if enabled else "disabled",
                kb_id,
            )

    async def get_enabled_tools(self, user_id: int) -> list[int]:
        """Return IDs of reactive tools enabled for the user."""
        res = await self.get_enabled_resources(user_id)
        return res["tool_ids"]

    async def get_enabled_knowledge_bases(self, user_id: int) -> list[int]:
        """Return IDs of reactive KBs enabled for the user."""
        kbs = await self._kb_repo.list_enabled_for_reactive(user_id)
        return [kb.id for kb in kbs]

    async def get_enabled_resources(self, user_id: int) -> dict:
        """Return both IDs and names of enabled reactive tools and KBs."""
        from sqlalchemy import select
        from backend.domain.models.integration_instance import IntegrationInstance
        from backend.application.integrations.service import IntegrationService

        stmt = select(IntegrationInstance).where(
            IntegrationInstance.user_id == user_id,
            IntegrationInstance.is_enabled.is_(True),
            IntegrationInstance.available_in_reactive.is_(True),
        )
        result = await self._session.execute(stmt)
        instances = result.scalars().all()

        integration_service = IntegrationService(self._session)
        tool_ids = []
        tool_names = []
        for instance in instances:
            discovered = await integration_service._discover_tools(instance)
            for t in discovered:
                tool_name = t["name"]
                tool_id = abs(hash(f"{instance.id}:{tool_name}")) % 1000000 + 1
                tool_ids.append(tool_id)
                tool_names.append(tool_name)

        kbs = await self._kb_repo.list_enabled_for_reactive(user_id)

        return {
            "tool_ids": tool_ids,
            "tool_names": tool_names,
            "kb_ids": [kb.id for kb in kbs],
            "kb_names": [kb.name for kb in kbs],
        }

    async def has_any_config(self, user_id: int) -> bool:
        """Return True if the user has enabled at least one reactive tool or KB."""
        res = await self.get_enabled_resources(user_id)
        return bool(res["tool_ids"] or res["kb_ids"])

