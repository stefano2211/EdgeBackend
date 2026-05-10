"""Reactive Document repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistencia.models.reactive_document import ReactiveDocument
from src.persistencia.repositories.base_repository import BaseRepository


class ReactiveDocumentRepository(BaseRepository[ReactiveDocument]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ReactiveDocument)

    async def list_by_knowledge_base(self, kb_id: int) -> list[ReactiveDocument]:
        stmt = (
            select(ReactiveDocument)
            .where(ReactiveDocument.reactive_knowledge_base_id == kb_id)
            .order_by(ReactiveDocument.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_file_id(self, file_id: str) -> ReactiveDocument | None:
        stmt = select(ReactiveDocument).where(ReactiveDocument.file_id == file_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
