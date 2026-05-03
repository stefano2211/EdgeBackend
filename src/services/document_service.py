"""Document service — CRUD for uploaded documents with MinIO S3 storage."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.core.logging import logging
from src.persistencia.models.document import Document
from src.persistencia.repositories.document_repository import DocumentRepository
from src.persistencia.storage.storage_port import StoragePort
from src.services._helpers import commit_and_refresh

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StoragePort | None = None,
    ) -> None:
        self.session = session
        self.repo = DocumentRepository(session)
        self._storage = storage

    async def create_document(
        self,
        kb_id: int,
        user_id: int,
        filename: str,
        s3_key: str,
        content_type: str | None = None,
    ) -> Document:
        """Create a document record with its S3 key already set."""
        from src.services.knowledge_service import KnowledgeService
        kb_service = KnowledgeService(self.session)
        kb = await kb_service.get_knowledge_base(kb_id, user_id)

        doc = Document(
            knowledge_base_id=kb.id,
            file_id=s3_key,
            filename=filename,
            content_type=content_type,
            status="uploaded",
        )
        await self.repo.create(doc)
        await commit_and_refresh(self.session, doc)
        return doc

    async def list_documents(
        self, knowledge_base_id: int | None = None
    ) -> list[Document]:
        """List documents, optionally filtered by knowledge base."""
        if knowledge_base_id is not None:
            return await self.repo.list_by_knowledge_base(knowledge_base_id)
        return await self.repo.list()

    async def delete_document(self, doc_id: int) -> None:
        """Delete document from DB and remove its object from MinIO."""
        doc = await self.repo.get_by_id(doc_id)
        if not doc:
            raise NotFoundError(f"Document {doc_id} not found")

        if self._storage is not None:
            try:
                await self._storage.delete(doc.file_id)
                logger.info("Deleted object from MinIO: %s", doc.file_id)
            except FileNotFoundError:
                logger.warning("Object not found in MinIO (already deleted): %s", doc.file_id)
            except Exception:
                logger.exception("Failed to delete object from MinIO: %s", doc.file_id)

        await self.repo.delete(doc)
        await self.session.commit()

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
