"""Knowledge base service — CRUD for knowledge bases."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate
from src.core.exceptions import NotFoundError
from src.core.logging import logging
from src.persistencia.models.knowledge_base import KnowledgeBase
from src.persistencia.repositories.knowledge_repository import KnowledgeRepository
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort
from src.services._helpers import commit_and_refresh, apply_patch

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        session: AsyncSession,
        vector_repo: VectorStorePort | None = None,
    ) -> None:
        self.session = session
        self.kb_repo = KnowledgeRepository(session)
        self._vector_repo = vector_repo

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def list_knowledge_bases(self, user_id: int, context_mode: str | None = None) -> list[KnowledgeBase]:
        return await self.kb_repo.list_by_user(user_id, context_mode)

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
        kb = await self.get_knowledge_base(kb_id, user_id)
        try:
            await self.vector_repo.delete_collection(knowledge_base_id=kb_id)
            logger.info("Deleted Qdrant collection kb_%d", kb_id)
        except Exception:
            logger.warning("Qdrant collection kb_%d not found or already deleted", kb_id)
        await self.kb_repo.delete(kb)
        await self.session.commit()

    async def get_knowledge_base_with_documents(self, kb_id: int, user_id: int) -> KnowledgeBase:
        return await self.get_knowledge_base(kb_id, user_id)
