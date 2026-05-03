"""Document service — CRUD for uploaded documents."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.persistencia.models.document import Document
from src.persistencia.repositories.document_repository import DocumentRepository
from src.services._helpers import commit_and_refresh


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DocumentRepository(session)

    async def create_document(self, kb_id: int, user_id: int, filename: str) -> Document:
        """Create a document record. File upload handled in router."""
        from src.services.knowledge_service import KnowledgeService
        kb_service = KnowledgeService(self.session)
        kb = await kb_service.get_knowledge_base(kb_id, user_id)

        doc = Document(
            knowledge_base_id=kb.id,
            filename=filename,
            status="uploaded",
        )
        await self.repo.create(doc)
        await commit_and_refresh(self.session, doc)
        return doc

    async def update_document_status(
        self, doc_id: int, status: str, qdrant_collection: str | None = None
    ) -> Document:
        doc = await self.repo.get_by_id(doc_id)
        if not doc:
            raise NotFoundError(f"Document {doc_id} not found")
        doc.status = status
        if qdrant_collection:
            doc.qdrant_collection = qdrant_collection
        await commit_and_refresh(self.session, doc)
        return doc
