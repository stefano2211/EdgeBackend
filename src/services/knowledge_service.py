"""Knowledge service: CRUD + document upload tracking."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate
from src.core.exceptions import NotFoundError, ConflictError
from src.core.logging import logging
from src.persistencia.models.knowledge_base import KnowledgeBase
from src.persistencia.models.document import Document
from src.persistencia.repositories.knowledge_repository import KnowledgeRepository
from src.persistencia.repositories.document_repository import DocumentRepository
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        session: AsyncSession,
        vector_repo: VectorStorePort | None = None,
    ) -> None:
        self.session = session
        self.kb_repo = KnowledgeRepository(session)
        self.doc_repo = DocumentRepository(session)
        self._vector_repo = vector_repo

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def list_knowledge_bases(self, user_id: int, context_mode: str | None = None) -> list[KnowledgeBase]:
        return await self.kb_repo.list_by_user(user_id, context_mode)

    async def create_knowledge_base(self, user_id: int, data: KnowledgeBaseCreate) -> KnowledgeBase:
        kb = KnowledgeBase(
            user_id=user_id,
            name=data.name,
            description=data.description,
            context_mode=data.context_mode,
        )
        await self.kb_repo.create(kb)
        await self.session.commit()
        await self.session.refresh(kb)
        return kb

    async def get_knowledge_base(self, kb_id: int, user_id: int) -> KnowledgeBase:
        kb = await self.kb_repo.get_by_id_for_user(kb_id, user_id)
        if not kb:
            raise NotFoundError(f"Knowledge base {kb_id} not found")
        return kb

    async def update_knowledge_base(
        self, kb_id: int, user_id: int, data: KnowledgeBaseUpdate
    ) -> KnowledgeBase:
        kb = await self.get_knowledge_base(kb_id, user_id)
        if data.name is not None:
            kb.name = data.name
        if data.description is not None:
            kb.description = data.description
        await self.session.commit()
        await self.session.refresh(kb)
        return kb

    async def delete_knowledge_base(self, kb_id: int, user_id: int) -> None:
        kb = await self.get_knowledge_base(kb_id, user_id)
        # Cleanup Qdrant collection for this KB
        try:
            await self.vector_repo.delete_by_doc_id(
                knowledge_base_id=kb_id, doc_id="*"
            )
            logger.info("Deleted Qdrant collection kb_%d", kb_id)
        except Exception:
            logger.warning("Qdrant collection kb_%d not found or already deleted", kb_id)
        await self.kb_repo.delete(kb)
        await self.session.commit()

    async def get_knowledge_base_with_documents(self, kb_id: int, user_id: int) -> KnowledgeBase:
        kb = await self.get_knowledge_base(kb_id, user_id)
        # Eager load documents via relationship (selectin configured in model)
        return kb

    # ── Documents ──

    async def create_document(self, kb_id: int, user_id: int, filename: str) -> Document:
        """Create a document record. File upload handled in router."""
        kb = await self.get_knowledge_base(kb_id, user_id)
        doc = Document(
            knowledge_base_id=kb.id,
            filename=filename,
            status="uploaded",
        )
        await self.doc_repo.create(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def update_document_status(self, doc_id: int, status: str, qdrant_collection: str | None = None) -> Document:
        doc = await self.doc_repo.get_by_id(doc_id)
        if not doc:
            raise NotFoundError(f"Document {doc_id} not found")
        doc.status = status
        if qdrant_collection:
            doc.qdrant_collection = qdrant_collection
        await self.session.commit()
        await self.session.refresh(doc)
        return doc
