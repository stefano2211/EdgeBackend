"""Background document processing: parse → chunk → embed → index in Qdrant."""

import asyncio
import os

from src.core.config import settings
from src.core.logging import logging
from src.core.database import AsyncSessionLocal
from src.services.document_parser import parse_document
from src.services.chunking_service import chunk_text
from src.services.embedding_service import embed_texts
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort
from src.persistencia.repositories.document_repository import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Processes uploaded documents asynchronously.

    Args:
        vector_repo: Optional vector store implementation. Defaults to VectorRepository().

    Pipeline:
    1. Parse document (PDF/TXT → raw text + metadata)
    2. Chunk text (RecursiveCharacterTextSplitter, 512 chars, ~200 tokens)
    3. Generate embeddings (batch_size=64, normalized)
    4. Upsert chunks to Qdrant via VectorRepository
    5. Update document status to "indexed"
    """

    def __init__(self, vector_repo: VectorStorePort | None = None) -> None:
        self._vector_repo = vector_repo

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def _resolve_file_path(self, file_id: str) -> str | None:
        """Resolve file path on disk (non-blocking via thread)."""
        base_path = os.path.join(settings.UPLOAD_DIR, file_id)
        if await asyncio.to_thread(os.path.exists, base_path):
            return base_path
        files = await asyncio.to_thread(os.listdir, settings.UPLOAD_DIR)
        for f in files:
            if f.startswith(file_id):
                return os.path.join(settings.UPLOAD_DIR, f)
        return None

    async def process_document(
        self,
        doc_id: int,
        knowledge_base_id: int,
    ) -> None:
        """Process a single document in a fresh DB session with transaction safety."""
        async with AsyncSessionLocal() as session:
            doc_repo = DocumentRepository(session)

            doc = await doc_repo.get_by_id(doc_id)
            if not doc:
                logger.error("Document %s not found for processing", doc_id)
                return

            try:
                # Update status to processing
                doc.status = "processing"
                await session.commit()

                # Resolve file path
                file_path = await self._resolve_file_path(doc.file_id)
                if not file_path:
                    raise FileNotFoundError(f"File not found for document {doc_id}")

                # 1. Parse (returns dict with text + metadata)
                parsed = await parse_document(file_path)
                raw_text = parsed["text"]
                parse_meta = parsed["metadata"]
                if not raw_text.strip():
                    raise ValueError("No text extracted from document")

                # 2. Chunk (uses RecursiveCharacterTextSplitter defaults)
                chunks = chunk_text(raw_text)
                if not chunks:
                    raise ValueError("No chunks generated")

                # 3. Embed (batch_size=64, normalized for cosine similarity)
                embeddings = await embed_texts(chunks, batch_size=64, normalize=True)

                # 4. Upsert to Qdrant via repository
                collection_name = f"kb_{knowledge_base_id}"
                await self.vector_repo.upsert_chunks(
                    knowledge_base_id=knowledge_base_id,
                    chunks=chunks,
                    embeddings=embeddings,
                    metadata={
                        "filename": doc.filename,
                        "knowledge_base_id": knowledge_base_id,
                        "total_pages": parse_meta.get("total_pages"),
                    },
                    doc_id=doc_id,
                )

                # 5. Update status
                doc.status = "indexed"
                doc.qdrant_collection = collection_name
                await session.commit()
                logger.info(
                    "Document %d indexed successfully in %s (%d chunks)",
                    doc_id,
                    collection_name,
                    len(chunks),
                )

            except Exception:
                logger.exception("Failed to process document %d", doc_id)
                await session.rollback()
                doc.status = "failed"
                await session.commit()
