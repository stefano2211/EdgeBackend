"""Document repository with knowledge base lookups."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.models.document import Document
from backend.infrastructure.persistence.base_repository import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Document)

    async def list_by_knowledge_base(self, kb_id: int) -> list[Document]:
        stmt = select(Document).where(Document.knowledge_base_id == kb_id).order_by(Document.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_file_id(self, file_id: str) -> Document | None:
        stmt = select(Document).where(Document.file_id == file_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
