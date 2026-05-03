"""ToolConfig and MCPSource repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.tool_config import ToolConfig, MCPSource
from src.persistencia.repositories.base_repository import BaseRepository


class ToolRepository(BaseRepository[ToolConfig]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ToolConfig)

    async def get_by_name(self, name: str) -> ToolConfig | None:
        stmt = select(ToolConfig).where(ToolConfig.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_source(self, source_id: int) -> list[ToolConfig]:
        stmt = select(ToolConfig).where(ToolConfig.source_id == source_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_enabled(self) -> list[ToolConfig]:
        stmt = select(ToolConfig).where(ToolConfig.is_enabled == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class MCPSourceRepository(BaseRepository[MCPSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MCPSource)

    async def list_enabled(self) -> list[MCPSource]:
        stmt = select(MCPSource).where(MCPSource.is_enabled == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()
