"""Document service — CRUD for uploaded documents with MinIO S3 storage."""

from __future__ import annotations

import os
import uuid as uuid_mod

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.exceptions import NotFoundError
from backend.core.logging import logging
from backend.domain.models.document import Document
from backend.infrastructure.persistence.document_repository import DocumentRepository
from backend.infrastructure.storage.storage_port import StoragePort
from backend.core._helpers import commit_and_refresh

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
            from backend.application.knowledge.service import KnowledgeService
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

    async def upload_document(
        self,
        kb_id: int,
        user_id: int,
        file: UploadFile,
    ) -> Document:
        """Orchestrate a full upload: validate size, store in MinIO, create DB record.

        Returns the created Document.  The caller (router) is responsible for
        scheduling the background processing task so that the FastAPI
        ``BackgroundTasks`` machinery stays in the web layer.
        """
        if self._storage is None:
            raise RuntimeError("DocumentService requires a StoragePort to perform uploads")

        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise ValueError(
                f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes"
            )

        ext = os.path.splitext(file.filename or "")[1]
        file_id = str(uuid_mod.uuid4())
        s3_key = f"kb/{kb_id}/{file_id}{ext}"
        content_type = file.content_type or "application/octet-stream"

        await self._storage.upload(s3_key, content, content_type=content_type)

        return await self.create_document(
            kb_id,
            user_id,
            file.filename or "unknown",
            s3_key=s3_key,
            content_type=content_type,
        )

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
        from backend.persistencia.vector import VectorRepository
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
