"""Knowledge base service — CRUD for knowledge bases with cascade cleanup."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate
from backend.core.exceptions import NotFoundError
from backend.core.logging import logging
from backend.domain.models.knowledge_base import KnowledgeBase
from backend.infrastructure.persistence.knowledge_repository import KnowledgeRepository
from backend.infrastructure.storage.storage_port import StoragePort
from backend.persistencia.vector import VectorRepository
from backend.infrastructure.vector.vector_store_port import VectorStorePort
from backend.core._helpers import commit_and_refresh, apply_patch

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        session: AsyncSession,
        vector_repo: VectorStorePort | None = None,
        storage: StoragePort | None = None,
    ) -> None:
        self.session = session
        self.kb_repo = KnowledgeRepository(session)
        self._vector_repo = vector_repo
        self._storage = storage

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def list_knowledge_bases(self, user_id: int) -> list[KnowledgeBase]:
        return await self.kb_repo.list_by_user(user_id)

    async def create_knowledge_base(self, user_id: int, data: KnowledgeBaseCreate) -> KnowledgeBase:
        kb = KnowledgeBase(**data.model_dump(), user_id=user_id)
        await self.kb_repo.create(kb)
        await commit_and_refresh(self.session, kb)
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
        apply_patch(kb, data)
        await commit_and_refresh(self.session, kb)
        return kb

    async def delete_knowledge_base(self, kb_id: int, user_id: int) -> None:
        """Delete knowledge base and all associated data.

        Order: DB commit first, then external systems. This prevents orphaned DB
        references if an external deletion fails.
        """
        kb = await self.get_knowledge_base(kb_id, user_id)

        # 1. Delete from Relational DB first (source of truth).
        #    Documents cascade automatically via SQLAlchemy ORM + DB FK.
        await self.kb_repo.delete(kb)
        await self.session.commit()
        logger.info("Deleted knowledge base %d from DB", kb_id)

        # 2. Delete Qdrant collection (best-effort)
        try:
            await self.vector_repo.delete_collection(knowledge_base_id=kb_id)
            logger.info("Deleted Qdrant collection kb_%d", kb_id)
        except Exception:
            logger.warning("Qdrant collection kb_%d not found or already deleted", kb_id)

        # 3. Delete all document objects from MinIO (prefix isolation) (best-effort)
        if self._storage is not None:
            try:
                deleted = await self._storage.delete_prefix(f"kb/{kb_id}/")
                logger.info("Deleted %d objects from MinIO for kb_%d", deleted, kb_id)
            except Exception:
                logger.exception("Failed to delete MinIO objects for kb_%d", kb_id)

    async def get_knowledge_base_with_documents(self, kb_id: int, user_id: int) -> KnowledgeBase:
        return await self.get_knowledge_base(kb_id, user_id)

    async def toggle_chat(self, kb_id: int, user_id: int, enabled: bool) -> KnowledgeBase:
        kb = await self.get_knowledge_base(kb_id, user_id)
        kb.is_enabled_chat = enabled
        await commit_and_refresh(self.session, kb)
        return kb

    async def toggle_reactive(self, kb_id: int, user_id: int, enabled: bool) -> KnowledgeBase:
        kb = await self.get_knowledge_base(kb_id, user_id)
        kb.is_enabled_reactive = enabled
        await commit_and_refresh(self.session, kb)
        return kb
