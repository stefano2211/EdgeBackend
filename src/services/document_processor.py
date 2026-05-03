"""Background document processing: download from MinIO → parse → chunk → embed → index in Qdrant."""

from __future__ import annotations

from src.core.logging import logging
from src.core.database import AsyncSessionLocal
from src.services.document_parser import parse_document_bytes, ParsedDocument
from src.services.chunking_service import chunk_documents, Chunk
from src.services.embedding_service import embed_texts
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort
from src.persistencia.repositories.document_repository import DocumentRepository
from src.persistencia.storage.storage_port import StoragePort

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    End-to-end document processing pipeline.

    Pipeline:
    1. Download bytes from MinIO/S3 (file_id is the full S3 key)
    2. Parse document bytes (PDF/TXT/CSV/JSON → text + per-page metadata)
    3. Chunk with metadata preservation (RecursiveCharacterTextSplitter)
    4. Generate embeddings (batch_size=64, normalized)
    5. Upsert chunks + metadata to Qdrant
    6. Update document status
    """

    def __init__(
        self,
        vector_repo: VectorStorePort | None = None,
        storage: StoragePort | None = None,
    ) -> None:
        self._vector_repo = vector_repo
        self._storage = storage

    @property
    def vector_repo(self) -> VectorStorePort:
        if self._vector_repo is None:
            self._vector_repo = VectorRepository()
        return self._vector_repo

    async def _download(self, s3_key: str) -> bytes:
        """Download document bytes from object storage."""
        if self._storage is None:
            from src.persistencia.storage import MinioStorageRepository
            self._storage = MinioStorageRepository()
        return await self._storage.download(s3_key)

    async def _parse(self, data: bytes, filename: str) -> ParsedDocument:
        """Parse document bytes asynchronously."""
        return await parse_document_bytes(data, filename=filename)

    async def _chunk(
        self,
        parsed: ParsedDocument,
        doc_id: int,
        filename: str,
    ) -> list[Chunk]:
        """Split parsed text into metadata-rich chunks."""
        return chunk_documents(
            parsed.text,
            doc_id=doc_id,
            filename=filename,
            base_metadata=parsed.metadata,
        )

    async def _embed(self, chunks: list[Chunk]) -> list[list[float]]:
        """Generate embeddings for all chunk texts."""
        texts = [c.text for c in chunks]
        return await embed_texts(texts, batch_size=64, normalize=True)

    async def _index(
        self,
        knowledge_base_id: int,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        doc_id: int,
    ) -> None:
        """Upsert chunks with per-chunk metadata to vector store."""
        chunk_texts = [c.text for c in chunks]
        # Each chunk carries its own metadata (chunk_index, filename, page_number, etc.)
        meta_list = [c.metadata for c in chunks]
        await self.vector_repo.upsert_chunks(
            knowledge_base_id=knowledge_base_id,
            chunks=chunk_texts,
            embeddings=embeddings,
            metadata=meta_list,
            doc_id=doc_id,
        )

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
                # 0. Update status to processing
                doc.status = "processing"
                await session.commit()

                # 1. Download from MinIO/S3 (file_id is the full S3 key)
                data = await self._download(doc.file_id)
                if not data:
                    raise ValueError(f"Empty file downloaded for document {doc_id}")

                # 2. Parse
                parsed = await self._parse(data, doc.filename)
                if not parsed.text.strip():
                    raise ValueError("No text extracted from document")

                # 3. Chunk (with metadata preservation)
                chunks = await self._chunk(parsed, doc_id, doc.filename)
                if not chunks:
                    raise ValueError("No chunks generated")

                # 4. Embed
                embeddings = await self._embed(chunks)

                # 5. Index
                collection_name = f"kb_{knowledge_base_id}"
                await self._index(knowledge_base_id, chunks, embeddings, doc_id)

                # 6. Finalize
                doc.status = "indexed"
                doc.qdrant_collection = collection_name
                await session.commit()
                logger.info(
                    "Document %d indexed successfully in %s (%d chunks, parser=%s)",
                    doc_id,
                    collection_name,
                    len(chunks),
                    parsed.metadata.get("parser", "unknown"),
                )

            except Exception:
                logger.exception("Failed to process document %d", doc_id)
                await session.rollback()
                doc.status = "failed"
                await session.commit()
