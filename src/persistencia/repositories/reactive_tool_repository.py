"""Reactive ToolConfig and MCPSource repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.reactive_tool_config import ReactiveToolConfig
from src.persistencia.models.reactive_mcp_source import ReactiveMCPSource
from src.persistencia.repositories.base_repository import BaseRepository


class ReactiveToolRepository(BaseRepository[ReactiveToolConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReactiveToolConfig)

    async def get_by_name(self, name: str) -> ReactiveToolConfig | None:
        stmt = select(ReactiveToolConfig).where(ReactiveToolConfig.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_name_and_source(self, name: str, source_id: int) -> ReactiveToolConfig | None:
        stmt = select(ReactiveToolConfig).where(
            ReactiveToolConfig.name == name,
            ReactiveToolConfig.source_id == source_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_source(self, source_id: int) -> list[ReactiveToolConfig]:
        stmt = select(ReactiveToolConfig).where(ReactiveToolConfig.source_id == source_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_user(self, user_id: int) -> list[ReactiveToolConfig]:
        stmt = select(ReactiveToolConfig).where(ReactiveToolConfig.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_enabled_by_user(self, user_id: int) -> list[ReactiveToolConfig]:
        stmt = select(ReactiveToolConfig).where(
            ReactiveToolConfig.user_id == user_id,
            ReactiveToolConfig.is_enabled == True,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ReactiveMCPSourceRepository(BaseRepository[ReactiveMCPSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReactiveMCPSource)

    async def list_by_user(self, user_id: int) -> list[ReactiveMCPSource]:
        stmt = select(ReactiveMCPSource).where(ReactiveMCPSource.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_enabled_by_user(self, user_id: int) -> list[ReactiveMCPSource]:
        stmt = select(ReactiveMCPSource).where(
            ReactiveMCPSource.user_id == user_id,
            ReactiveMCPSource.is_enabled == True,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
