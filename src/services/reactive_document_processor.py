"""Background reactive document processing: download → parse → chunk → embed → index.

Pipeline identical to chat documents but indexes into isolated Qdrant
collections prefixed with ``reactive_kb_``.
"""

from __future__ import annotations

from src.core.config import settings
from src.core.logging import logging
from src.core.database import AsyncSessionLocal
from src.services.document_parser import parse_document_bytes, ParsedDocument
from src.services.chunking_service import chunk_documents, contextualize_chunks, Chunk
from src.services.embedding_service import embed_texts
from src.persistencia.vector import VectorRepository
from src.persistencia.vector.vector_store_port import VectorStorePort, SparseVector
from src.persistencia.repositories.reactive_document_repository import ReactiveDocumentRepository
from src.persistencia.storage.storage_port import StoragePort

logger = logging.getLogger(__name__)


class ReactiveDocumentProcessor:
    """End-to-end document processing pipeline for the reactive system."""

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

    async def _contextualize(
        self, chunks: list[Chunk], full_text: str
    ) -> list[Chunk]:
        """Apply Anthropic contextual chunking if enabled."""
        if not settings.CONTEXTUAL_CHUNKING_ENABLED:
            logger.debug("Contextual chunking disabled, skipping")
            return chunks

        try:
            return await contextualize_chunks(chunks, full_text)
        except Exception as e:
            logger.warning("Contextual chunking failed, using raw chunks: %s", e)
            return chunks

    async def _embed_dense(self, chunks: list[Chunk]) -> list[list[float]]:
        """Generate dense embeddings for all chunk texts."""
        texts = [c.text for c in chunks]
        return await embed_texts(texts, batch_size=64, normalize=True)

    async def _embed_sparse(self, chunks: list[Chunk]) -> list[SparseVector] | None:
        """Generate sparse BM25 embeddings for all chunk texts."""
        if not settings.HYBRID_SEARCH_ENABLED:
            return None

        try:
            from src.services.sparse_embedding_service import embed_sparse_texts

            texts = [c.text for c in chunks]
            return await embed_sparse_texts(texts)
        except ImportError:
            logger.warning("fastembed not available; skipping sparse embeddings")
            return None
        except Exception as e:
            logger.warning("Sparse embedding failed: %s", e)
            return None

    async def _index(
        self,
        knowledge_base_id: int,
        chunks: list[Chunk],
        dense_embeddings: list[list[float]],
        sparse_embeddings: list[SparseVector] | None,
        doc_id: int,
    ) -> None:
        """Upsert chunks with dual vectors (dense + sparse) to vector store."""
        chunk_texts = [c.text for c in chunks]
        meta_list = [c.metadata for c in chunks]
        await self.vector_repo.upsert_chunks(
            knowledge_base_id=knowledge_base_id,
            chunks=chunk_texts,
            embeddings=dense_embeddings,
            metadata=meta_list,
            doc_id=doc_id,
            sparse_embeddings=sparse_embeddings,
            prefix="reactive_kb_",
        )

    async def process_document(
        self,
        doc_id: int,
        knowledge_base_id: int,
    ) -> None:
        """Process a single reactive document in a fresh DB session."""
        async with AsyncSessionLocal() as session:
            doc_repo = ReactiveDocumentRepository(session)

            doc = await doc_repo.get_by_id(doc_id)
            if not doc:
                logger.error("Reactive document %s not found for processing", doc_id)
                return

            try:
                # 0. Update status to processing
                doc.status = "processing"
                await session.commit()

                # 1. Download from MinIO/S3
                data = await self._download(doc.file_id)
                if not data:
                    raise ValueError(f"Empty file downloaded for reactive document {doc_id}")

                # 2. Parse
                parsed = await self._parse(data, doc.filename)
                if not parsed.text.strip():
                    raise ValueError("No text extracted from document")

                # 3. Chunk
                chunks = await self._chunk(parsed, doc_id, doc.filename)
                if not chunks:
                    raise ValueError("No chunks generated")

                # 4. Contextualize
                chunks = await self._contextualize(chunks, parsed.text)

                # 5. Embed (dense)
                dense_embeddings = await self._embed_dense(chunks)

                # 6. Embed (sparse)
                sparse_embeddings = await self._embed_sparse(chunks)

                # 7. Index (dual vectors to Qdrant)
                collection_name = f"reactive_kb_{knowledge_base_id}"
                await self._index(
                    knowledge_base_id, chunks, dense_embeddings,
                    sparse_embeddings, doc_id,
                )

                # 8. Finalize
                doc.status = "indexed"
                doc.qdrant_collection = collection_name
                await session.commit()
                logger.info(
                    "Reactive document %d indexed successfully in %s "
                    "(%d chunks, contextual=%s, sparse=%s)",
                    doc_id,
                    collection_name,
                    len(chunks),
                    settings.CONTEXTUAL_CHUNKING_ENABLED,
                    sparse_embeddings is not None,
                )

            except Exception:
                logger.exception("Failed to process reactive document %d", doc_id)
                await session.rollback()
                doc.status = "failed"
                await session.commit()
