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
        knowledge_service = None,
    ) -> None:
        self.session = session
        self.repo = DocumentRepository(session)
        self._storage = storage
        self._knowledge_service = knowledge_service

    def _get_knowledge_service(self):
        if self._knowledge_service is None:
            from src.services.knowledge_service import KnowledgeService
            self._knowledge_service = KnowledgeService(self.session)
        return self._knowledge_service

    async def create_document(
        self,
        kb_id: int,
        user_id: int,
        filename: str,
        s3_key: str,
        content_type: str | None = None,
    ) -> Document:
        """Create a document record with its S3 key already set."""
        kb = await self._get_knowledge_service().get_knowledge_base(kb_id, user_id)

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
        """Delete document from DB, remove its object from MinIO, and delete its vectors from Qdrant.

        Order: DB commit first, then external systems. This prevents orphaned DB
        references if an external deletion fails.
        """
        doc = await self.repo.get_by_id(doc_id)
        if not doc:
            raise NotFoundError(f"Document {doc_id} not found")

        kb_id = doc.knowledge_base_id
        file_id = doc.file_id

        # 1. Delete from Relational DB first (source of truth)
        await self.repo.delete(doc)
        await self.session.commit()
        logger.info("Deleted document %d from DB", doc_id)

        # 2. Delete from Qdrant vector database (best-effort)
        from src.persistencia.vector import VectorRepository
        vector_repo = VectorRepository()
        try:
            await vector_repo.delete_by_doc_id(kb_id, doc_id)
            logger.info("Deleted vectors for document %d from Qdrant", doc_id)
        except Exception:
            logger.exception("Failed to delete vectors for document %d", doc_id)

        # 3. Delete from MinIO storage (best-effort)
        if self._storage is not None:
            try:
                await self._storage.delete(file_id)
                logger.info("Deleted object from MinIO: %s", file_id)
            except FileNotFoundError:
                logger.warning("Object not found in MinIO (already deleted): %s", file_id)
            except Exception:
                logger.exception("Failed to delete object from MinIO: %s", file_id)

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
